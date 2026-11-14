"""Time Sheets tabs keep one row per employee per week. No live Sheets."""
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from test_equipment_squawks import FakeSpreadsheet, FakeWorksheet, _exec_equipment_helpers


class UpdatingWorksheet(FakeWorksheet):
    """Worksheet with a range update, like gspread."""

    def update(self, values=None, range_name=None, value_input_option=None):
        self.writes.append(("update", range_name, [list(r) for r in values]))
        start, _end = range_name.split(":")
        row_number = int("".join(ch for ch in start if ch.isdigit()))
        self.rows[row_number - 1] = list(values[0])


class UpdatingSpreadsheet(FakeSpreadsheet):
    def add_worksheet(self, title, rows=0, cols=0):
        self.added.append(title)
        ws = UpdatingWorksheet(title)
        self.sheets[title] = ws
        return ws


def _when(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("America/Los_Angeles"))


class TimesheetUpsertTests(unittest.TestCase):
    def setUp(self):
        self.s = _exec_equipment_helpers()

    def _record(self, employee, hours, entry, stamp, initials="RC"):
        return self.s["build_timesheet_record"](
            employee, date(2026, 11, 8),
            day_values={"Sun": {"Location": "Field", "CVH Hours": hours}},
            initials=initials, when=_when(stamp), entry_id=entry, today=date(2026, 11, 11),
        )

    def _each_book(self):
        return (FakeSpreadsheet(), UpdatingSpreadsheet())

    def test_resave_overwrites_same_employee_week_row(self):
        s = self.s
        for book in self._each_book():
            s["save_timesheet_record"](self._record("Ron Cline", "8", "TS-1", "2026-11-14 10:00:00"), spreadsheet=book)
            s["save_timesheet_record"](self._record("Barry Markham", "7", "TS-B", "2026-11-14 10:05:00", "BM"), spreadsheet=book)
            s["save_timesheet_record"](self._record("Ron Cline", "9", "TS-2", "2026-11-14 11:00:00"), spreadsheet=book)
            ws = book.sheets["Time Sheets"]
            header = ws.rows[0]
            self.assertEqual(len(ws.rows), 3)  # header + Ron + Barry
            self.assertEqual(ws.rows[0], header)
            ron = dict(zip(header, ws.rows[1]))
            self.assertEqual(ron["Employee"], "Ron Cline")
            self.assertEqual(ron["Entry ID"], "TS-2")
            self.assertEqual(ron["Sun CVH Hours"], "9")
            barry = dict(zip(header, ws.rows[2]))
            self.assertEqual(barry["Entry ID"], "TS-B")
            self.assertEqual(barry["Sun CVH Hours"], "7")
            latest = s["latest_timesheet_record"](s["load_timesheet_records_readonly"](book), "Ron Cline", date(2026, 11, 8))
            self.assertEqual(latest["Entry ID"], "TS-2")

    def test_new_week_or_new_employee_appends(self):
        s = self.s
        book = UpdatingSpreadsheet()
        s["save_timesheet_record"](self._record("Ron Cline", "8", "TS-1", "2026-11-14 10:00:00"), spreadsheet=book)
        other_week = s["build_timesheet_record"](
            "Ron Cline", date(2026, 11, 15),
            day_values={"Sun": {"Location": "Field", "CVH Hours": "5"}},
            initials="RC", when=_when("2026-11-21 10:00:00"), entry_id="TS-3", today=date(2026, 11, 18),
        )
        s["save_timesheet_record"](other_week, spreadsheet=book)
        self.assertEqual(len(book.sheets["Time Sheets"].rows), 3)

    def test_existing_duplicates_update_latest_and_never_delete(self):
        s = self.s
        book = UpdatingSpreadsheet()
        # Build two legacy duplicate rows the old append-only way, newest second.
        ws, _ = s["ensure_timesheets_worksheet"](book)
        header = ws.rows[0]

        def row_for(rec):
            return [str(rec.get(c, "")) for c in header]

        old = self._record("Ron Cline", "6", "TS-OLD", "2026-11-14 09:00:00")
        new = self._record("Ron Cline", "8", "TS-NEW", "2026-11-14 10:00:00")
        ws.append_row(row_for(new))   # newest first on purpose: order in the sheet must not matter
        ws.append_row(row_for(old))
        before_old = list(ws.rows[2])
        s["save_timesheet_record"](self._record("Ron Cline", "10", "TS-FIX", "2026-11-14 12:00:00"), spreadsheet=book)
        self.assertEqual(len(ws.rows), 3)
        self.assertEqual(dict(zip(header, ws.rows[1]))["Entry ID"], "TS-FIX")   # newest row replaced
        self.assertEqual(ws.rows[2], before_old)                                 # older duplicate untouched
        self.assertEqual(ws.rows[0], header)

    def test_header_is_never_rewritten(self):
        s = self.s
        book = UpdatingSpreadsheet()
        s["save_timesheet_record"](self._record("Ron Cline", "8", "TS-1", "2026-11-14 10:00:00"), spreadsheet=book)
        s["save_timesheet_record"](self._record("Ron Cline", "9", "TS-2", "2026-11-14 11:00:00"), spreadsheet=book)
        for write in book.sheets["Time Sheets"].writes:
            if write[0] == "update":
                self.assertFalse(write[1].startswith("A1:"))
            if write[0] == "update_cell":
                self.assertGreater(write[1], 1)

    def test_anthony_tab_also_one_row_per_week(self):
        s = self.s

        def rec(hours, entry, stamp):
            return s["build_anthony_timesheet_record"](
                "Anthony Root", date(2026, 11, 8),
                day_values={"Sun": {"Survery Hrs": hours}},
                initials="AR", when=_when(stamp), entry_id=entry, today=date(2026, 11, 11),
            )

        for book in self._each_book():
            s["save_anthony_timesheet_record"](rec("5", "AT-1", "2026-11-14 10:00:00"), spreadsheet=book)
            s["save_anthony_timesheet_record"](rec("6", "AT-2", "2026-11-14 11:00:00"), spreadsheet=book)
            ws = book.sheets["Anthony Time Sheets"]
            self.assertEqual(len(ws.rows), 2)
            self.assertEqual(dict(zip(ws.rows[0], ws.rows[1]))["Entry ID"], "AT-2")

    def test_mail_audit_tab_still_appends_every_send(self):
        s = self.s
        book = UpdatingSpreadsheet()
        record = self._record("Ron Cline", "8", "TS-1", "2026-11-14 10:00:00")
        for index in range(3):
            audit = s["build_timesheet_mail_audit_record"](
                record, action="Send", pin_employee="Ron Cline", status="Sent",
                idempotency_key="k" + str(index), when=_when("2026-11-14 12:0%d:00" % index),
            )
            s["save_timesheet_mail_audit_record"](audit, spreadsheet=book)
        self.assertEqual(len(book.sheets[s["TIMESHEET_MAIL_SHEET_TITLE"]].rows), 4)


if __name__ == "__main__":
    unittest.main()
