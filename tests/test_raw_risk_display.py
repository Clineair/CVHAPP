"""Current assessment displays raw risk only; storage and safety rules stay intact."""
import unittest
from streamlit.testing.v1 import AppTest
from test_aircraft_weights import offline_app


class RawRiskDisplayTests(unittest.TestCase):
    def test_boundary_scores_display_and_unchanged_gates(self):
        at = AppTest.from_string(offline_app(), default_timeout=30).run()
        # Use real sliders and classification across every FAR mode, not a test copy.
        boundaries = [(0, "Low Risk"), (30, "Low Risk"), (31, "Medium Risk"),
                      (39, "Medium Risk"), (60, "Medium Risk"), (61, "High Risk")]
        cases = [(part, score, category) for part in ["Part 91", "Part 135", "Part 137", "Part 133"]
                 for score, category in boundaries]
        for part, score, category in cases:
            with self.subTest(part=part, score=score):
                at.segmented_control[0].set_value(part).run()
                remaining = score
                for slider in at.slider:
                    value = min(10, remaining)
                    slider.set_value(value)
                    remaining -= value
                self.assertEqual(remaining, 0)
                at.run()
                self.assertFalse(list(at.exception))
                current = [m.value for m in at.markdown if m.value.startswith("### ") and "Risk" in m.value]
                self.assertEqual(len(current), 1)
                self.assertIn(f"{score} — {category}", current[0])
                self.assertNotIn("%", current[0])
                self.assertNotIn("/", current[0])
                self.assertFalse(any("conic-gradient" in m.value for m in at.markdown))
                self.assertTrue(any(c.value == "Low 0–30 · Medium 31–60 · High 61+" for c in at.caption))
                # No current-assessment Markdown exposes a percentage or fraction.
                self.assertFalse(any("%" in m.value or f"{score} / " in m.value
                                     for m in at.markdown if "Risk" in m.value))
                if category == "Medium Risk":
                    self.assertTrue(any(a.label == "Mitigations (required for Medium risk)" for a in at.text_area))
                    self.assertTrue(any("approves this flight" in c.label for c in at.checkbox))
                if category == "High Risk":
                    self.assertTrue(any("High risk cannot be accepted" in m.value for m in at.markdown))
                else:
                    self.assertTrue(any("NOT RELEASED" in m.value for m in at.markdown))
        # An explicit failed stop remains NO-GO even with a zero raw risk score.
        for slider in at.slider:
            slider.set_value(0)
        next(r for r in at.radio if "No" in r.options).set_value("No")
        at.run()
        self.assertTrue(any("NO-GO" in m.value and "Stop item answered No" in m.value for m in at.markdown))


if __name__ == "__main__":
    unittest.main()
