# Employee receipts

Each employee page (EMPLOYEES → name) has **Time Sheet** and **🧾 Receipts**
buttons. Receipts uses the same PIN as the time sheet, and a remembered phone
opens only that employee's receipts.

## What an employee does

1. Tap **🧾 Receipts**, then **🧾 Add a receipt**.
2. **Take a photo** (in-page camera) or **Upload a photo or PDF** (on a phone
   this also offers the full camera).
3. The app reads the photo and fills in Date, Amount, Receipt number, and
   Vendor. The employee checks them and types the Purpose and any notes.
4. **Receipt complete** checks the date, amount, and purpose. Then the
   **Allocate to category** menu appears.
5. **Save receipt** uploads the photo to Drive and adds one row to the
   **Receipts** tab (created on the first save).
6. **My receipts** lists their receipts with totals per category for this pay
   period, last pay period, or all time.

## Categories

`employee_receipts.RECEIPT_CATEGORIES` is the only list. Edit it to add,
remove, or reorder categories. Saved rows keep whatever category they had.

## Photo reading

- PDF: text read with pypdf (same as the BL2 bulletin pre-fill).
- Photo (JPEG/PNG/WebP): Tesseract OCR through `pytesseract`. Streamlit Cloud
  installs Tesseract from `packages.txt`. If Tesseract is missing the form says
  so and the employee types the fields.
- HEIC: stored, not read. iPhones normally send JPEG to the browser.

## Storage

- Sheet: `Receipts` tab of the CVH FRAT Log spreadsheet. Columns:
  Saved At, Entry ID, Employee, Date, Amount, Receipt Number, Vendor, Purpose,
  Category, Photo Link, Photo File, Notes. No other tab is written; the FRAT
  log header is never touched.
- Drive: `apps_script/receipt_upload` (see its README) with Streamlit secrets
  `[receipts] apps_script_url` and `upload_token`. One subfolder per employee.
  If not set up, the row still saves with the file name and the employee is
  told to keep the paper receipt.

## Summary email to Patti

- From the company mailbox in `[timesheet_company_mail]` (clineair891@gmail.com,
  Gmail app password), to Patti (`[timesheet_mail].recipient`, or
  `[receipts_mail].recipient` if set).
- Per employee: category totals, then each receipt with its Drive photo link.
- Pay periods are two weeks, Sunday to Saturday, counted from Sunday
  2026-11-15 (`RECEIPTS_PERIOD_ANCHOR`). A receipt counts in the period it was
  saved, so a late receipt is never missed or counted twice.
- **Manual:** Ron Cline's Receipts page has **Receipts summary email to Patti**:
  pick the period, preview, tick the confirm box, press **Send receipts
  summary**. Each send is logged in a `Receipts Mail` tab and a second send of
  the same period needs **Send it again**.
- **Automatic (OFF):** `tools/send_receipts_summary.py --send` sends on the
  Monday after a period ends, only if `[receipts_mail] auto_send = true`.
  `deploy/receipts-summary/receipts-summary.yml` is a parked GitHub Actions
  schedule (Mondays 7:30 AM PST). To turn it on: copy it to
  `.github/workflows/`, add repo secret `CVH_STREAMLIT_SECRETS`, set repo
  variable `RECEIPTS_AUTO_SEND = true`, and set `auto_send = true`.
