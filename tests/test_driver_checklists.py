"""BNSF HELI2 spray checklist under Driver > Checklists. Mocks only; no Sheets."""
import unittest
from pathlib import Path

import driver_checklists as dc


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PY = REPO_ROOT / "app.py"

# Exact wording from Ron's 24 Nov 2026 workbook "BNSF Spray Check List.xlsx".
EXPECTED_ITEMS = (
    (1, "Fuel: Aircraft / Vehicle / 2-Gal Fuel Can for Pump (1 per truck)", "Full", None, False),
    (2, "Oil: Aircraft & Vehicle", "4 qt. ea.", None, False),
    (3, "Fuel Filters: Aircraft & Vehicle", "1 each", "check on spares", False),
    (4, "Portable Tool Box", "Full", None, False),
    (5, "Torque Wrenches", "2", None, True),
    (6, "Radios w headsets & Chargers", "3", None, False),
    (7, "Six-Outlet Surge Protector", "1", None, False),
    (8, "Covers for Aircraft: Bubble / Head / Tail Rotor", "3", None, False),
    (9, "Wheels for Aircraft", "2", None, False),
    (10, "Hearing Protection", "2", None, True),
    (11, "Gloves: Chemical & Work / Mix Coats", "4 each", None, False),
    (12, "Tire chains / per Helitruck", "1 set", None, False),
    (13, "Battery Start Pack (24 volt)", "1", None, False),
    (14, "Jumper Cables", "1", None, False),
    (15, "Jump Box (12 volt)", "1", None, False),
    (16, "Battery Charger (12 volt)", "1", None, True),
    (17, "Grease Gun & Grease (480 t/r Aeroshell)", "1 each", None, True),
    (18, "Prist & White Cloth Rags", "1 & 1 pack", None, False),
    (19, "Paper Towels", "1 Roll", None, False),
    (20, "Dry Brake & Load Hoses & suction screen / per truck", "1 each", None, False),
    (21, "Chemical suction hose and meter", "1", None, False),
    (22, "iPad / Phones chargers & mounts", "1 each", "H3 mount", False),
    (23, "Pilot Gel Cushions", "2", None, True),
    (24, "Driver's Log Book / EZ ELD", "1 each", None, False),
    (25, "Spill Kit per truck / coveralls / eyewash / soap", "Full", None, False),
    (26, "Extra Spray Nozzle Parts / Fittings", "All", "review nozzles with white restrictors", False),
    (27, "Extra Pull Rope & Spark Plug for Pumps", "1 each", None, False),
    (28, "Load Secured Properly", "All", None, False),
    (29, "Pre-Check Vehicles: Lights/Wipers/Heat/Horn/Tires-Air Pressure", "All", None, False),
    (30, "Fire Extinguisher: HeliTruck & Aircraft", "2 each & 1", None, False),
    (31, "Triangles / per truck", "1 set", None, False),
    (32, "Ice Scraper", "1", None, True),
    (33, "Battery Drill / Driver", "1", None, True),
    (34, "Di-electrical grease (Check Jet Fuel electrical connections)", "1", None, False),
    (35, "PPE / Hard hat, Safety Glasses, Safety Vest,", None, None, False),
    (36, "Safety Toe Boots", None, None, False),
)

OLD_PLACEHOLDERS = (
    "Confirm proximity to BNSF rail line",
    "Verify no spraying over or near railroad tracks",
    "Check BNSF specific safety protocols",
    "Confirm altitude and swath width for BNSF area",
    "Verify no drift risk to rail corridor",
)


class BnsfHeli2SprayChecklistTests(unittest.TestCase):
    def test_title_and_dropdown_label(self):
        self.assertEqual(dc.BNSF_HELI2_SPRAY_TITLE, "RR Spray Check List")
        self.assertEqual(dc.BNSF_HELI2_SPRAY_LABEL, "BNSF HELI2 Spray")

    def test_items_match_workbook_wording_order_and_notes(self):
        items = dc.BNSF_HELI2_SPRAY_CHECKLIST
        self.assertEqual(len(items), 36)
        self.assertEqual([item["number"] for item in items], list(range(1, 37)))
        for item, expected in zip(items, EXPECTED_ITEMS):
            number, description, qty, note, emphasis = expected
            self.assertEqual(item["number"], number)
            self.assertEqual(item["description"], description)
            self.assertEqual(item["qty"], qty)
            self.assertEqual(item["note"], note)
            self.assertEqual(item["emphasis"], emphasis)

    def test_labels_use_en_dash_qty_and_keep_items_without_qty(self):
        fuel = dc.BNSF_HELI2_SPRAY_CHECKLIST[0]
        self.assertEqual(
            dc.format_checklist_item_label(fuel),
            "Fuel: Aircraft / Vehicle / 2-Gal Fuel Can for Pump (1 per truck) \u2013 Full",
        )
        ppe = dc.BNSF_HELI2_SPRAY_CHECKLIST[34]
        self.assertEqual(
            dc.format_checklist_item_label(ppe),
            "PPE / Hard hat, Safety Glasses, Safety Vest,",
        )
        boots = dc.BNSF_HELI2_SPRAY_CHECKLIST[35]
        self.assertEqual(dc.format_checklist_item_label(boots), "Safety Toe Boots")
        self.assertEqual(dc.checklist_item_key(fuel), "bnsf_heli2_spray_1")

    def test_app_wires_new_list_and_leaves_other_job_types(self):
        source = APP_PY.read_text(encoding="utf-8")
        self.assertIn("import driver_checklists", source)
        self.assertIn('"driver_checklists"', source)
        self.assertIn("driver_checklists.BNSF_HELI2_SPRAY_LABEL", source)
        self.assertIn("driver_checklists.BNSF_HELI2_SPRAY_CHECKLIST", source)
        self.assertIn("driver_checklists.BNSF_HELI2_SPRAY_TITLE", source)
        self.assertIn('["Forestry", "Mt. Vernon", "Seeding", "Local Spraying", driver_checklists.BNSF_HELI2_SPRAY_LABEL, "Survey"]', source)
        self.assertNotIn('elif checklist_type == "BNSF":', source)
        for placeholder in OLD_PLACEHOLDERS:
            self.assertNotIn(placeholder, source)
        # Other job-type lists stay in place.
        self.assertIn('if checklist_type == "Survey":', source)
        self.assertIn('elif checklist_type == "Forestry":', source)
        self.assertIn('elif checklist_type == "Mt. Vernon":', source)
        self.assertIn('elif checklist_type in ["Seeding", "Local Spraying"]:', source)
        self.assertIn('st.checkbox("Fuel for Aircraft/Vehicle – Full")', source)
        self.assertIn('st.checkbox("Check seed hopper calibration and rate")', source)

    def test_must_check_items_have_red_tag_and_unchanged_wording(self):
        self.assertEqual(dc.MUST_CHECK_LEGEND, "Red = must check")
        self.assertEqual(dc.MUST_CHECK_TAG, "MUST CHECK")
        self.assertEqual(dc.MUST_CHECK_COLOR, "#FF0000")
        must = [item for item in dc.BNSF_HELI2_SPRAY_CHECKLIST if dc.is_must_check(item)]
        names = [item["description"] for item in must]
        self.assertEqual(
            names,
            [
                "Torque Wrenches",
                "Hearing Protection",
                "Battery Charger (12 volt)",
                "Grease Gun & Grease (480 t/r Aeroshell)",
                "Pilot Gel Cushions",
                "Ice Scraper",
                "Battery Drill / Driver",
            ],
        )
        self.assertEqual(len(must), 7)
        legend = dc.must_check_legend_html()
        self.assertIn("Red = must check", legend)
        self.assertIn("#FF0000", legend)
        wrenches = must[0]
        label = dc.format_checklist_item_label(wrenches)
        self.assertEqual(label, "Torque Wrenches \u2013 2")
        self.assertNotIn("MUST CHECK", label)
        visible = dc.must_check_item_html(wrenches)
        self.assertIn("<strong>MUST CHECK</strong>", visible)
        self.assertIn("#FF0000", visible)
        self.assertIn(label, visible)
        fuel = dc.BNSF_HELI2_SPRAY_CHECKLIST[0]
        self.assertFalse(dc.is_must_check(fuel))
        self.assertNotIn("MUST CHECK", dc.format_checklist_item_label(fuel))

    def test_app_shows_must_check_legend_and_tag(self):
        source = APP_PY.read_text(encoding="utf-8")
        self.assertIn("driver_checklists.must_check_legend_html()", source)
        self.assertIn("driver_checklists.must_check_item_html(item)", source)
        self.assertIn("driver_checklists.is_must_check(item)", source)
        self.assertIn('label_visibility="collapsed"', source)


if __name__ == "__main__":
    unittest.main()
