# BLT bulletin PDF uploader (Google Apps Script)

This web app runs as the Google account that deploys it (clineair891), so
uploaded bulletin PDFs are owned by that account and use its Drive quota.

## Script Properties

In the Apps Script project, set:

- `UPLOAD_TOKEN` — the same value as Streamlit secret `[blt_checks] upload_token`
- `FOLDER_ID` — the destination Drive folder id
  (`1m4yapRPCqmpC4QiBmWg683I4TZsfmpsa` for Ron's existing My Drive folder)

Do not put these values in `Code.gs`.

## Deploy

1. In [script.google.com](https://script.google.com), signed in as clineair891@gmail.com,
   create a project and paste `Code.gs` and `appsscript.json`.
2. Set the Script Properties above.
3. Deploy → New deployment → Type: Web app.
   - Execute as: Me (clineair891@gmail.com) (`USER_DEPLOYING`)
   - Who has access: Anyone (`ANYONE_ANONYMOUS`)
4. Copy the web app URL into Streamlit secret `[blt_checks] apps_script_url`.
5. Put the same `UPLOAD_TOKEN` value in Streamlit secret `[blt_checks] upload_token`.

The Python app posts JSON `{token, filename, base64}` and follows the Apps Script
302 to `googleusercontent`. If the URL or token is missing, or the call fails,
the BLT check still saves and only the filename is stored.
