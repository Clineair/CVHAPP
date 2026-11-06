"""Zero defaults never reset ongoing factor entries or bypass existing release gates."""
import unittest
from streamlit.testing.v1 import AppTest
from test_aircraft_weights import offline_app


class ZeroRiskDefaultTests(unittest.TestCase):
    def test_fresh_zero_defaults_and_preserved_entries_each_part(self):
        for part in ["Part 91", "Part 133", "Part 135", "Part 137"]:
            with self.subTest(part=part):
                at = AppTest.from_string(offline_app(), default_timeout=30).run()
                at.segmented_control[0].set_value(part).run()
                self.assertFalse(list(at.exception))
                self.assertTrue(len(at.slider) > 0)
                self.assertTrue(all(s.value == 0 for s in at.slider))
                self.assertTrue(all(s.min == 0 and s.max == 10 for s in at.slider))
                self.assertTrue(any("0 — Risk review incomplete" in m.value for m in at.markdown))
                self.assertTrue(any("NOT RELEASED" in m.value for m in at.markdown))
                self.assertTrue(at.button(key=f"frat_{part}_save").disabled)
                self.assertTrue(all(r.value is None for r in at.radio if "No" in r.options))
                self.assertIsNone(at.selectbox(key="frat_sig").value)
                self.assertFalse(at.checkbox(key=f"frat_{part}_accept").value)
                self.assertTrue(any("Review every factor" in c.value for c in at.caption))
                key = at.slider[0].key
                at.slider(key=key).set_value(7).run()
                self.assertEqual(at.slider(key=key).value, 7)
                self.assertTrue(any("7 — Risk review incomplete" in m.value for m in at.markdown))
                at.run()
                self.assertEqual(at.slider(key=key).value, 7)
                at.selectbox[0].select("Enstrom 480").run()
                self.assertEqual(at.slider(key=key).value, 7)
                self.assertFalse(list(at.exception))


if __name__ == "__main__":
    unittest.main()
