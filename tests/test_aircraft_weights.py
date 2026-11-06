"""Offline weight and Streamlit regression checks; no credentials or live Sheets used.

Run: python3 -m unittest discover -s tests -v
"""
import ast
import hashlib
import json
from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1] / "app.py"
SOURCE = APP.read_text()
TREE = ast.parse(SOURCE)


def isolated_weights():
    nodes = [n for n in TREE.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "AIRCRAFT_DATA" for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name in ("aircraft_empty_weight", "aircraft_total_weight"))]
    scope = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), "exec"), scope)
    return scope


def offline_app():
    # Replace only network/credential boundaries in a copy of the real app AST.
    # No app code, credentials, live Sheets or local secret files are changed/read.
    tree = ast.parse(SOURCE)
    replacements = {
        "frat_sheet_url": 'def frat_sheet_url():\n    return "https://docs.google.com/spreadsheets/d/offline-test/edit"',
        "_gsheets_worksheet": 'def _gsheets_worksheet():\n    return OfflineWorksheet()',
    }
    tree.body = [ast.parse(replacements[n.name]).body[0]
                 if isinstance(n, ast.FunctionDef) and n.name in replacements else n
                 for n in tree.body]
    stub = '''
class OfflineWorksheet:
    def row_values(self, row):
        rows = st.session_state.get("_test_rows", [])
        return rows[0] if rows else []
    def append_row(self, row, **kwargs):
        if "_test_rows" not in st.session_state:
            st.session_state["_test_rows"] = []
        st.session_state["_test_rows"].append(row)
    def get_all_records(self):
        return []
'''
    return stub + "\n" + ast.unparse(tree)


WEIGHTS = {"Robinson R44 Raven II": ("N893PC", 1596, 1772), "Enstrom 480": ("N480ML", 1822, 2013)}
PARTS = ["Part 91", "Part 133", "Part 135", "Part 137"]


class WeightTests(unittest.TestCase):
    def test_production_sheet_schema_unchanged(self):
        names = {"PARTS", "CORE_FACTORS", "PART_FACTORS", "PART_STOPS", "CONFIG_FIELDS",
                 "ALL_FACTOR_KEYS", "ALL_STOP_KEYS", "FRAT_COLUMNS"}
        nodes = [n for n in TREE.body if
                 (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))
                 or (isinstance(n, ast.FunctionDef) and n.name == "_unique")]
        scope = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), "exec"), scope)
        # Hash of the exact pre-change production header, including field order.
        self.assertEqual(hashlib.sha256(json.dumps(scope["FRAT_COLUMNS"]).encode()).hexdigest(),
                         "f4b28b40aa9f60bf256574455cdab0d0ba642420cc368e1dca2490a7ec400eb0")

    def test_both_aircraft_all_parts(self):
        scope = isolated_weights()
        for name, (registration, baseline, equipped) in WEIGHTS.items():
            data = scope["AIRCRAFT_DATA"][name]
            for part in PARTS:
                with self.subTest(aircraft=registration, part=part):
                    empty = equipped if part == "Part 137" else baseline
                    self.assertEqual(data["registration"], registration)
                    self.assertEqual(scope["aircraft_empty_weight"](data, part), empty)
                    payload = 20 * 8.34 if part == "Part 137" else 100
                    self.assertAlmostEqual(scope["aircraft_total_weight"](data, part, 190, 25, payload),
                                           empty + 190 + 25 * data["fuel_weight_per_gal"] + payload)
                    self.assertEqual(scope["aircraft_total_weight"](data, part, 0, 0, 0), empty)


class StreamlitTests(unittest.TestCase):
    def test_switching_totals_and_offline_saved_records(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(offline_app(), default_timeout=30).run()
        self.assertFalse(list(at.exception))
        # Reuse one session, including 137 -> baseline modes and repeated aircraft changes.
        for name in ["Enstrom 480", "Robinson R44 Raven II", "Enstrom 480"]:
            registration, baseline, equipped = WEIGHTS[name]
            for part in ["Part 137", "Part 91", "Part 133", "Part 135"]:
                with self.subTest(aircraft=registration, part=part):
                    at.selectbox[0].select(name)
                    at.segmented_control[0].set_value(part).run()
                    self.assertFalse(list(at.exception))
                    expected_empty = equipped if part == "Part 137" else baseline
                    empty_metric = next(m for m in at.metric if "empty weight" in m.label)
                    self.assertIn(registration, empty_metric.label)
                    self.assertEqual("with spray gear" in empty_metric.label, part == "Part 137")
                    self.assertEqual(empty_metric.value, f"{expected_empty:,} lbs")
                    inputs = {i.label: i for i in at.number_input}
                    inputs["Pilot Weight (lbs)"].set_value(190)
                    inputs["Fuel (gal)"].set_value(25)
                    if part == "Part 137":
                        inputs["Hopper / Spray load (gal)"].set_value(20)
                        inputs["Product density (lb/gal)"].set_value(9.0)
                    at.run()
                    expected_total = expected_empty + 190 + 25 * (6.0 if registration == "N893PC" else 6.7) + (180 if part == "Part 137" else 0)
                    total = next(m for m in at.metric if m.label in ("Total Weight", "Total Internal Weight"))
                    self.assertEqual(total.value, f"{expected_total:.0f} lbs")
                    aircraft_display = next(i for i in at.text_input if i.label == "Aircraft (from configuration)")
                    self.assertTrue(aircraft_display.disabled)
                    self.assertTrue(aircraft_display.value.startswith(registration))
                    if registration == "N480ML" and part == "Part 135":
                        self.assertTrue(any("not approved" in w.value for w in at.warning))
                    # Sign and save a deliberately NO-GO record to the offline worksheet only.
                    next(r for r in at.radio if "No" in r.options).set_value("No")
                    at.selectbox(key="frat_sig").select("Ronald A Cline")
                    at.checkbox(key=f"frat_{part}_accept").check().run()
                    at.button(key=f"frat_{part}_save").click().run()
                    self.assertFalse(list(at.exception))
                    rows = at.session_state["_test_rows"]
                    record = dict(zip(rows[0], rows[-1]))
                    self.assertEqual(record["aircraft"], registration)
                    self.assertEqual(record["part"], part)
                    self.assertEqual(record["internal_weight"], str(round(expected_total)))
                    self.assertEqual(record["pilot_signature"], "Ronald A Cline")
                    self.assertEqual(record["decision"], "NO-GO")
                    self.assertEqual(len(rows[0]), len(rows[-1]))
                    self.assertEqual(sum("Open FRAT Google Sheet" in b.proto.label for b in at.get("link_button")), 2)


if __name__ == "__main__":
    unittest.main()
