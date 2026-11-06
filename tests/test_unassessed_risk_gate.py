"""Zero is an unassessed sentinel, never an automatically accepted risk score."""
import unittest
from streamlit.testing.v1 import AppTest
from test_aircraft_weights import offline_app


class UnassessedRiskGateTests(unittest.TestCase):
    def test_review_gate_and_existing_requirements_each_far(self):
        for part in ["Part 91", "Part 133", "Part 135", "Part 137"]:
            with self.subTest(part=part):
                at = AppTest.from_string(offline_app(), default_timeout=30).run()
                at.segmented_control[0].set_value(part).run()
                self.assertTrue(at.button(key=f"frat_{part}_save").disabled)
                self.assertTrue(any("0 — Risk review incomplete" in m.value for m in at.markdown))
                warnings = "\n".join(w.value for w in at.warning)
                self.assertIn("0 = not assessed", warnings)
                self.assertTrue(all(s.label in warnings for s in at.slider))
                # Reviewing every factor alone must not bypass stops or signature.
                for slider in at.slider:
                    slider.set_value(1)
                at.run()
                self.assertFalse(any("risk review incomplete" in w.value for w in at.warning))
                self.assertTrue(any("NOT RELEASED" in m.value for m in at.markdown))
                self.assertTrue(at.button(key=f"frat_{part}_save").disabled)
                # Even all other requirements fulfilled cannot release an all-zero review.
                for slider in at.slider:
                    slider.set_value(0)
                for radio in at.radio:
                    if "Yes" in radio.options:
                        radio.set_value("Yes")
                at.selectbox(key="frat_sig").select("Ronald A Cline")
                at.checkbox(key=f"frat_{part}_accept").check().run()
                self.assertTrue(at.button(key=f"frat_{part}_save").disabled)
                self.assertTrue(any("NOT RELEASED" in m.value for m in at.markdown))
                # A mixed review with total >30 remains incomplete, even with approvals.
                last_key = at.slider[-1].key
                for i, slider in enumerate(at.slider):
                    slider.set_value([10, 10, 10, 9][i] if i < 4 else (0 if slider.key == last_key else 1))
                at.run()
                at.text_area(key=f"frat_{part}_mitigations").set_value("Offline test mitigation")
                at.checkbox(key=f"frat_{part}_approved").check().run()
                self.assertGreater(sum(s.value for s in at.slider), 30)
                self.assertTrue(at.button(key=f"frat_{part}_save").disabled)
                self.assertTrue(any("NOT RELEASED" in m.value for m in at.markdown))
                self.assertFalse(any(" — Medium Risk" in m.value and m.value.startswith("###") for m in at.markdown))
                # No auto-bump; unrelated rerun and aircraft switch retain exact scores.
                entered = {s.key: s.value for s in at.slider}
                at.selectbox[0].select("Enstrom 480").run()
                self.assertEqual({s.key: s.value for s in at.slider}, entered)
                at.slider(key=last_key).set_value(1).run()
                self.assertFalse(list(at.exception))
                self.assertFalse(any("risk review incomplete" in w.value for w in at.warning))
                self.assertTrue(any("✅ GO" in m.value for m in at.markdown))
                self.assertFalse(at.button(key=f"frat_{part}_save").disabled)
                # Existing stop/approval gates still work after risk review is complete.
                at.checkbox(key=f"frat_{part}_approved").uncheck().run()
                self.assertTrue(at.button(key=f"frat_{part}_save").disabled)
                self.assertTrue(any("Medium-risk approval required" in m.value for m in at.markdown))
                next(r for r in at.radio if "No" in r.options).set_value("No").run()
                self.assertTrue(any("NO-GO" in m.value and "Stop item answered No" in m.value for m in at.markdown))
                # No live or offline save button was clicked by this test.
                self.assertNotIn("_test_rows", at.session_state)


if __name__ == "__main__":
    unittest.main()
