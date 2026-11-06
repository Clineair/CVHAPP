"""Explicit confirmed reset clears Pilot assessment state only, never saved records."""
import ast
from datetime import date, datetime
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo
from streamlit.testing.v1 import AppTest
from test_aircraft_weights import TREE, offline_app


class SessionState(dict):
    __setattr__ = dict.__setitem__


class AssessmentResetTests(unittest.TestCase):
    def test_callback_targets_all_modes_without_global_clear(self):
        kept = {"current_mode": "Pilot", "completed_checklists": ["kept"],
                "last_current_weight": 12345, "selected_heli": "Heli4",
                "last_max_water_gal": 123, "hist_part_filter": ["Part 137"],
                "_test_rows": [["saved"], ["record"]], "global_setting": "keep"}
        state = SessionState(kept)
        for part in ["Part 91", "Part 133", "Part 135", "Part 137"]:
            for suffix in ["pilot_exp", "stop_airworthy", "mitigations", "approver", "approved",
                           "ron_unreachable", "accept", "save", "save_success", "record_id"]:
                state[f"frat_{part}_{suffix}"] = "stale"
        state.update({"frat_pilot": "Anthony Root", "frat_sig": "Anthony Root", "frat_route": "Old job",
                      "frat_date": date(2020, 1, 1), "pax_w_0": 190, "pax_w_3": 210,
                      "pilot_config_fuel_gal": 75, "pilot_config_aircraft": "Enstrom 480",
                      "far_part": "Part 137", "far_part_ctrl": "Part 137"})
        nodes = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "reset_pilot_assessment"]
        scope = {"st": SimpleNamespace(session_state=state)}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "reset_callback", "exec"), scope)
        scope["reset_pilot_assessment"]()
        self.assertEqual(state, {**kept, "pilot_reset_pending": False})

    def test_confirm_cancel_defaults_and_no_saved_record_changes_all_modes(self):
        for part in ["Part 91", "Part 133", "Part 135", "Part 137"]:
            with self.subTest(part=part):
                at = AppTest.from_string(offline_app(), default_timeout=30).run()
                at.segmented_control[0].set_value(part).run()
                at.selectbox(key="pilot_config_aircraft").select("Enstrom 480").run()
                at.selectbox(key="frat_pilot").select("Anthony Root")
                at.selectbox(key="frat_sig").select("Anthony Root")
                at.date_input(key="frat_date").set_value(date(2020, 1, 1))
                at.text_input(key="frat_route").set_value("Unsaved flight")
                for i, slider in enumerate(at.slider):
                    slider.set_value(10 if i < 3 else 1)  # medium risk for all FAR modes
                for radio in at.radio:
                    if "Yes" in radio.options:
                        radio.set_value("Yes")
                for field in at.number_input:
                    field.set_value(1.0 if isinstance(field.value, float) else 1)
                at.checkbox(key=f"frat_{part}_accept").check().run()
                at.text_area(key=f"frat_{part}_mitigations").set_value("Unsaved mitigation")
                at.selectbox(key=f"frat_{part}_approver").select("Carl Mulvaney").run()
                at.checkbox(key=f"frat_{part}_ron_unreachable").check()
                at.checkbox(key=f"frat_{part}_approved").check().run()
                at.session_state["_test_rows"] = [["saved"], ["record"]]
                at.session_state["last_current_weight"] = 12345
                at.session_state["completed_checklists"] = ["kept"]
                # Normal rerun preserves entries; requesting reset cannot discard them.
                at.run()
                at.button(key="pilot_reset_request").click().run()
                self.assertEqual(at.text_input(key="frat_route").value, "Unsaved flight")
                at.button(key="pilot_reset_cancel").click().run()
                self.assertEqual(at.selectbox(key="frat_pilot").value, "Anthony Root")
                self.assertEqual(at.slider[0].value, 10)
                self.assertEqual(at.text_area(key=f"frat_{part}_mitigations").value, "Unsaved mitigation")
                self.assertTrue(at.checkbox(key=f"frat_{part}_approved").value)
                at.button(key="pilot_reset_request").click().run()
                at.button(key="pilot_reset_confirm").click().run()
                self.assertFalse(list(at.exception))
                self.assertFalse(at.session_state["pilot_reset_pending"])
                self.assertEqual(at.segmented_control[0].value, "Part 135")
                self.assertEqual(at.selectbox(key="pilot_config_aircraft").value, "Robinson R44 Raven II")
                self.assertIsNone(at.selectbox(key="frat_pilot").value)
                self.assertIsNone(at.selectbox(key="frat_sig").value)
                self.assertEqual(at.text_input(key="frat_route").value, "")
                self.assertEqual(at.date_input(key="frat_date").value,
                                 datetime.now(ZoneInfo("America/Los_Angeles")).date())
                self.assertTrue(all(s.value == 0 for s in at.slider))
                self.assertTrue(all(r.value is None for r in at.radio if "Yes" in r.options))
                self.assertFalse(at.checkbox(key="frat_Part 135_accept").value)
                self.assertEqual(at.text_area(key="frat_Part 135_mitigations").value, "")
                self.assertTrue(at.button(key="frat_Part 135_save").disabled)
                self.assertTrue(any("NOT RELEASED" in m.value for m in at.markdown))
                defaults = {"pilot_config_pressure_alt": 0, "pilot_config_oat_c": 15,
                            "pilot_config_pilot_weight": 200, "pilot_config_fuel_gal": 30,
                            "pilot_config_pax_count": 0, "pilot_config_pax_weight": 0,
                            "pilot_config_baggage": 0}
                for key, expected in defaults.items():
                    self.assertEqual(at.number_input(key=key).value, expected)
                self.assertEqual(at.session_state["_test_rows"], [["saved"], ["record"]])
                self.assertEqual(at.session_state["last_current_weight"], 12345)
                self.assertEqual(at.session_state["completed_checklists"], ["kept"])
                self.assertTrue(any(m.value == "1,596 lbs" for m in at.metric))
                # Revisit each operation: no old payload, review or approval state returns.
                for next_part in ["Part 91", "Part 133", "Part 137", "Part 135"]:
                    at.segmented_control[0].set_value(next_part).run()
                    self.assertTrue(all(s.value == 0 for s in at.slider))
                    self.assertTrue(all(r.value is None for r in at.radio if "Yes" in r.options))
                    self.assertFalse(at.checkbox(key=f"frat_{next_part}_accept").value)
                    for field in at.number_input:
                        if field.key not in defaults:
                            self.assertEqual(field.value, 8.34 if field.key == "pilot_config_density" else 0)
                # Positive review after reset still has blank approver and incomplete gates.
                for i, slider in enumerate(at.slider):
                    slider.set_value(10 if i < 3 else 1)
                at.run()
                self.assertIsNone(at.selectbox(key="frat_Part 135_approver").value)
                self.assertFalse(at.checkbox(key="frat_Part 135_approved").value)
                self.assertTrue(at.button(key="frat_Part 135_save").disabled)


if __name__ == "__main__":
    unittest.main()
