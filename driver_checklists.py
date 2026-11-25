"""Driver job-type checklists that live in code (not Google Sheets).

The BNSF HELI2 spray list replaces the old placeholder "BNSF" list under
Driver > Checklists. Wording, order, quantities, and notes come from Ron's
24 Nov 2026 workbook "BNSF Spray Check List.xlsx" (sheet title
"RR Spray Check List").

Items marked emphasis (red in the workbook) are MUST CHECK items.
"""

import html as html_lib

# Job-type option shown in the Driver checklist dropdown.
BNSF_HELI2_SPRAY_LABEL = "BNSF HELI2 Spray"

# Title cell from the workbook (D1).
BNSF_HELI2_SPRAY_TITLE = "RR Spray Check List"

# Same en dash the other Driver checklists use between description and qty.
QTY_SEPARATOR = " \u2013 "

# Ron: red in the workbook means the item must be checked.
MUST_CHECK_LEGEND = "Red = must check"
MUST_CHECK_TAG = "MUST CHECK"
MUST_CHECK_COLOR = "#FF0000"


def _item(number, description, qty=None, note=None, emphasis=False):
    return {
        "number": number,
        "description": description,
        "qty": qty,
        "note": note,
        "emphasis": bool(emphasis),
    }


# Items 37-40 in the workbook are numbered but blank; they are omitted.
BNSF_HELI2_SPRAY_CHECKLIST = (
    _item(1, "Fuel: Aircraft / Vehicle / 2-Gal Fuel Can for Pump (1 per truck)", "Full"),
    _item(2, "Oil: Aircraft & Vehicle", "4 qt. ea."),
    _item(3, "Fuel Filters: Aircraft & Vehicle", "1 each", note="check on spares"),
    _item(4, "Portable Tool Box", "Full"),
    _item(5, "Torque Wrenches", "2", emphasis=True),
    _item(6, "Radios w headsets & Chargers", "3"),
    _item(7, "Six-Outlet Surge Protector", "1"),
    _item(8, "Covers for Aircraft: Bubble / Head / Tail Rotor", "3"),
    _item(9, "Wheels for Aircraft", "2"),
    _item(10, "Hearing Protection", "2", emphasis=True),
    _item(11, "Gloves: Chemical & Work / Mix Coats", "4 each"),
    _item(12, "Tire chains / per Helitruck", "1 set"),
    _item(13, "Battery Start Pack (24 volt)", "1"),
    _item(14, "Jumper Cables", "1"),
    _item(15, "Jump Box (12 volt)", "1"),
    _item(16, "Battery Charger (12 volt)", "1", emphasis=True),
    _item(17, "Grease Gun & Grease (480 t/r Aeroshell)", "1 each", emphasis=True),
    _item(18, "Prist & White Cloth Rags", "1 & 1 pack"),
    _item(19, "Paper Towels", "1 Roll"),
    _item(20, "Dry Brake & Load Hoses & suction screen / per truck", "1 each"),
    _item(21, "Chemical suction hose and meter", "1"),
    _item(22, "iPad / Phones chargers & mounts", "1 each", note="H3 mount"),
    _item(23, "Pilot Gel Cushions", "2", emphasis=True),
    _item(24, "Driver's Log Book / EZ ELD", "1 each"),
    _item(25, "Spill Kit per truck / coveralls / eyewash / soap", "Full"),
    _item(26, "Extra Spray Nozzle Parts / Fittings", "All", note="review nozzles with white restrictors"),
    _item(27, "Extra Pull Rope & Spark Plug for Pumps", "1 each"),
    _item(28, "Load Secured Properly", "All"),
    _item(29, "Pre-Check Vehicles: Lights/Wipers/Heat/Horn/Tires-Air Pressure", "All"),
    _item(30, "Fire Extinguisher: HeliTruck & Aircraft", "2 each & 1"),
    _item(31, "Triangles / per truck", "1 set"),
    _item(32, "Ice Scraper", "1", emphasis=True),
    _item(33, "Battery Drill / Driver", "1", emphasis=True),
    _item(34, "Di-electrical grease (Check Jet Fuel electrical connections)", "1"),
    _item(35, "PPE / Hard hat, Safety Glasses, Safety Vest,"),
    _item(36, "Safety Toe Boots"),
)


def format_checklist_item_label(item):
    """Checkbox label: description, plus en-dash qty when the workbook has one."""
    description = item["description"]
    qty = item.get("qty")
    if qty is None or qty == "":
        return description
    return description + QTY_SEPARATOR + str(qty)


def checklist_item_key(item, prefix="bnsf_heli2_spray"):
    return "%s_%s" % (prefix, item["number"])


def is_must_check(item):
    """True for the seven workbook items whose Description was red."""
    return bool(item.get("emphasis"))


def must_check_legend_html():
    """One-line legend at the top of the list; color is not the only cue."""
    return (
        '<div style="color:%s;font-weight:bold">%s</div>'
        % (MUST_CHECK_COLOR, html_lib.escape(MUST_CHECK_LEGEND))
    )


def must_check_item_html(item):
    """Red visible line: MUST CHECK tag plus the unchanged item wording."""
    tag = html_lib.escape(MUST_CHECK_TAG)
    label = html_lib.escape(format_checklist_item_label(item))
    return (
        '<div style="color:%s"><strong>%s</strong> %s</div>'
        % (MUST_CHECK_COLOR, tag, label)
    )
