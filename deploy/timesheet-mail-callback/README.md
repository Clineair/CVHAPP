# Timesheet mail callback host

This folder is the deploy recipe for the standalone HTTPS callback in
`timesheet_mail_callback.py`. Streamlit does not start it.

The image runs as a non-root user. Python dependencies, including `requests`,
Firestore, and Secret Manager, are installed from `requirements.txt`.
Secrets and the serve override are not baked into the image. Set
`GOOGLE_CLOUD_PROJECT` and mount `TIMESHEET_MAIL_SECRETS_JSON` at runtime.
`TIMESHEET_MAIL_TOKEN_STORE=firestore` is the production default so more than
one Cloud Run instance can share short-lived OAuth state.

When a deploy is approved, use request-based Cloud Run in us-central1 with:

- `--min-instances=0` so the service can scale to zero
- `--max-instances=2` so this low-volume callback cannot fan out
- `--port=8080 --timeout=60 --concurrency=20`
- `--allow-unauthenticated` because the employee's browser must open the OAuth redirect

`--allow-unauthenticated` does not make the service a mail relay. `POST /timesheet-mail/redeem`, `/timesheet-mail/smtp-session`, and `/timesheet-mail/send` require a short-lived HMAC from Streamlit. The public OAuth routes only start or finish provider consent.

See `docs/TIMESHEET_AUTH.md` for the full external setup. Do not create a project, billing account, OAuth client, secret, or test email until that is explicitly approved.
