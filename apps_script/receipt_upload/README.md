# Employee receipt photo uploader (Google Apps Script)

Separate from the BL2 uploader so the working BL2 setup is not touched.
This web app runs as the account that deploys it (clineair891), so receipt
photos are owned by that account and use its Drive quota. Each employee gets
a subfolder (for example `Receipts/Carl Mulvaney/`) created on their first
receipt. The script only creates files. It never edits or deletes one.

Accepted: JPEG, PNG, WebP, HEIC/HEIF, and PDF, up to 15 MB. The first bytes
of each file are checked against its type.

## Script Properties

- `UPLOAD_TOKEN`: the same value as Streamlit secret `[receipts] upload_token`
- `RECEIPTS_FOLDER_ID`: the Drive folder id of the receipts folder (for
  example a new `CVH Receipts` folder in clineair891's My Drive)

Do not put these values in `Code.gs`.

## Deploy

1. In [script.google.com](https://script.google.com), signed in as
   clineair891@gmail.com, create a project and paste `Code.gs` and `appsscript.json`.
2. Set the Script Properties above.
3. Deploy → New deployment → Web app. Execute as: Me. Who has access: Anyone.
4. Put the web app URL in Streamlit secret `[receipts] apps_script_url` and the
   token in `[receipts] upload_token`.

Until those two secrets are set, a receipt still saves to the Receipts tab but
the employee is told the photo was NOT stored on Drive and to keep the paper copy.
