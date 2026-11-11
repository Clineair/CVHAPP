# Time-sheet sign-in and email

This document is the configuration and limitation guide for weekly time-sheet
access and direct in-app sending. Do not commit secrets, mailbox addresses, or
mail credentials. Sending stays off until the items below are all in place.

The app does not send mail in the current default configuration. There is no
Ron or shared mailbox sender. Each employee must send from their own authorized
mailbox, only to `patti@centralvalleyheli.com`, only after they review and
explicitly press Send.

## Implemented vs still a placeholder

**Implemented in this branch, but live sending stays off:**

- Time-sheet access for all six employees who have a form: the five official
  weekly forms, and Anthony Root's separate official form. Ron Cline has no
  time sheet.
- Official weekly mileage uses the IRS business rate that applies to the
  actual travel date, including a week that spans a rate change. Historic
  saved amounts are left alone. Anthony's form has no mileage fields.
- Preview of To, From, subject, body, and the official generated PDF
  attachment, with an explicit employee Send button.
- Fixed recipient `patti@centralvalleyheli.com`. Initials must still match
  the current week content. A duplicate send of the same employee + week +
  content hash already marked Sent is blocked.
- Google sign-in for time sheets (`st.login()` / `st.user` / `st.logout()`,
  reserved callback `/oauth2callback`). Sign-in email may differ from the
  send-from mailbox. Optional Microsoft sign-in remains in the code if a
  named `[auth.microsoft]` client is added later; it is **not** required for
  the current six employees.
- Official Gmail send path (Gmail API `gmail.send`, authorization-code +
  PKCE, session-only access token, mailbox email from official userinfo must
  match the configured send-from address).
- Official iCloud and Yahoo paths are recognized as SMTP + app-specific
  password, and stay fail-closed until a vault exists. Passwords are never
  collected in the app, chat, or Sheets.
- A standalone callback service in `timesheet_mail_callback.py` with `/healthz`,
  `/timesheet-mail/start`, and `/timesheet-mail/callback/gmail`, plus a
  Dockerfile recipe under `deploy/timesheet-mail-callback/`. It is not started
  by the Streamlit app and is not deployed.

**Still placeholders / not done (do not treat these as finished):**

- No callback host is deployed. There is no `fly.toml`, `render.yaml`, or
  `wrangler.toml`, and no live Cloud Run service.
- No OAuth clients, Streamlit `[auth]` secrets, mailbox maps, or SMTP vault
  have been created in this work. Secret *names* are documented here; secret
  values are not in the repo.
- `timesheet_email_can_send` stays False until `[timesheet_mail].enabled`,
  the Gmail send client, `[timesheet_mail_backend]`, and (for iCloud/Yahoo)
  a vaulted SMTP store are all present, plus identity, initials, PDF, and
  the fixed recipient.
- Microsoft Graph mail-send remains in the code for a future Hotmail or
  Outlook mailbox, but **no current employee uses it**, so a Microsoft
  mail-send app is not a current prerequisite.

## Current mailboxes (names and providers only)

Employee send-from addresses are not stored in the repo. Configure them later
only in Streamlit / backend secrets. Do not invent or commit real addresses.

For the current six time-sheet employees, the send-from providers are:

| Employee | Send-from provider |
| --- | --- |
| Carl Mulvaney | iCloud (SMTP + app-specific password, later) |
| Barry Markham | Yahoo (SMTP + app password, later) |
| Robert Rackley | Gmail (OAuth send) |
| Gary Grant | Gmail (OAuth send) |
| Skylar Fingerle | iCloud (SMTP + app-specific password, later) |
| Anthony Root | Gmail (OAuth send) |

There is no Hotmail, Outlook, or Microsoft 365 mailbox in this current set.
Do not register a Microsoft mail-send client unless a later roster change
needs one.

## Architectural decision: Streamlit Cloud cannot host the mail OAuth callback

Streamlit Community Cloud reserves `/oauth2callback` for `st.login()`. The app
cannot also receive a provider `form_post` response, and using the Streamlit
app URL as a second OAuth redirect would put an authorization code in the
browser query string and history, which this project forbids.

A second, separate HTTPS callback service is therefore a hard prerequisite for
Gmail sending. The Streamlit app never exchanges the authorization code, never
stores refresh tokens, and never puts access tokens in query parameters,
Sheets, the repo, logs, or another employee's session. Until that service is
deployed and the secrets above are present, `timesheet_email_can_send` stays
False.

Signing in with Google OpenID does not grant permission to send mail. Gmail
send uses a separate, least-privilege `gmail.send` consent and a short-lived
access token.

## Official provider support

| Provider | Official send method | Needed for current six? |
| --- | --- | --- |
| Gmail | OAuth 2.0 + Gmail API `gmail.send` (session-only access token; `access_type=online`) | Yes, for the three Gmail mailboxes. Requires the callback host and a separate Gmail send client. |
| iCloud Mail | **SMTP only** (`smtp.mail.me.com:587`, STARTTLS). Apple publishes no public OAuth or REST send API for third-party apps. Username is the full iCloud address. Password must be an [app-specific password](https://support.apple.com/en-us/102654) from account.apple.com (2FA required), never the Apple Account password. See [Apple Mail server settings](https://support.apple.com/en-us/102525). | Yes, later, for the two iCloud mailboxes. Fail closed until a vault exists. |
| Yahoo Mail | **SMTP** (`smtp.mail.yahoo.com:587` or `465`) with a [Yahoo app password](https://help.yahoo.com/kb/mail/generate-password-sln15241.html). Yahoo IMAP/SMTP OAuth (`mail-w`) exists only after a commercial access application; it is not self-serve in the developer console. | Yes, later, for the one Yahoo mailbox. Fail closed until a vault exists. |
| Microsoft 365, Outlook.com, Hotmail, Live.com | OAuth 2.0 + Microsoft Graph `Mail.Send` | **Not needed now.** Code remains fail-closed if a mailbox is later mapped to `microsoft`. |

App-specific passwords are long-lived secrets, which is a substantially
different architecture from session-only OAuth. This app will never ask an
employee for a mail password in chat or a form, and it will never store mail
credentials in Google Sheets or in a downloaded timesheet. Provision those
secrets later only into a secure backend or vault if you choose to enable
iCloud or Yahoo sending.

Do not treat a `mailto:` helper as fulfillment of in-app send.

## Identity for iCloud and Yahoo staff

Do not assume every employee has a Google mailbox. They do not need one to
*send*, because send-from and sign-in are configured separately.

For the current setup, time-sheet sign-in uses Streamlit's documented Google
OpenID Connect flow. An iCloud or Yahoo employee can sign in with a Google
account that is listed for them in `[timesheet_employees]`, then later send
from iCloud or Yahoo once the SMTP vault exists.

There is no official Streamlit iCloud or Yahoo login. Sign in with Apple would
need an [Apple Developer Program](https://developer.apple.com/programs/)
membership (currently $99 USD per year) and is not part of this step.
Optional Microsoft sign-in is already wired if `[auth.microsoft]` is added
later; it is not a current prerequisite because no current employee sends
from Hotmail or Outlook, and Google sign-in covers the planned access path.

If someone has neither a Google nor a Microsoft account, they cannot use
official Streamlit login until a later option (Apple, or a magic link after
the SMTP vault exists) is approved.

## Recommended callback host and verified cost

No callback host is deployed today. Existing artifacts in this repo are only
the Python scaffold, the Dockerfile recipe, and this document. There are no
hosting connectors installed in this bot, and no secrets file is in the
checkout.

**Recommended default: Google Cloud Run**, in the same Google Cloud project
you will already create for the Google sign-in client and the separate Gmail
send client. The existing Python callback can run there without a rewrite.

Official sources (checked 2026-11-11):

- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Google Cloud Free Tier](https://docs.cloud.google.com/free/docs/free-cloud-features)
- [Learn about Cloud Billing](https://docs.cloud.google.com/docs/get-started/learn-about-billing)

Request-based billing Free Tier (us-central1 / Tier 1, per billing account,
resets monthly):

- 2 million requests
- 180,000 vCPU-seconds
- 360,000 GB-seconds of memory
- 1 GB outbound data transfer from North America

At this app's expected volume (occasional employee sends), usage should stay
inside those limits, so the expected monthly Cloud Run cost is **$0**.

Honest caveats:

- Official documentation states that **a Google Cloud billing account is
  required** to use Google Cloud services, including Free Tier. A payment
  method is typically placed on file. Usage above the monthly limits is
  billed at standard rates.
- Published standard rates after the free amount (Tier 1, subject to change)
  are on the Cloud Run pricing page, including $0.40 per million requests,
  $0.0000240 per vCPU-second, and $0.0000025 per GiB-second, plus data
  transfer. Set a budget alert if you attach a billing account.
- This work does **not** create a project, billing account, or Cloud Run
  service until you explicitly approve that step.

**$0 alternative without a Google billing account: Cloudflare Workers Free.**
Official [Workers Paid vs Free limits](https://developers.cloudflare.com/workers/platform/pricing/):
$0/month, 100,000 requests/day, and 10 ms CPU per invocation on the Free plan
(Workers Paid is $5/month). This would require porting the Python scaffold to
JavaScript, and the 10 ms Free CPU cap may be tight for a token exchange.
It is the fallback if you do not want a Google billing account.

Render free instances spin down and are a poor fit for OAuth redirects. Paid
Render, Fly, or other hosts are not the recommendation.

## Streamlit Cloud / local sign-in setup

Do this in Google Cloud and Streamlit secrets after the callback-host decision.
Do not paste client secrets into the repo, chat, or logs.

1. In a Google Cloud project, configure the Google Auth Platform branding and
   audience as described in
   [Use the Google Auth Platform to authenticate users](https://docs.streamlit.io/develop/tutorials/authentication/google)
   and [st.login](https://docs.streamlit.io/develop/api-reference/user/st.login).
2. Create a **Web application** OAuth client used only for sign-in. Request the
   default Streamlit scopes only: `openid profile email`. Do **not** add
   `gmail.send` or other Gmail scopes to this client, and do **not** set
   Streamlit `expose_tokens`.
3. Authorized redirect URIs must be absolute and end with `/oauth2callback`:
   - Local: `http://localhost:8501/oauth2callback`
   - Live app: `https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/oauth2callback`
4. Install the Authlib extra on the host (`authlib>=1.3.2`, already listed in
   `requirements.txt`). Streamlit documents this as `streamlit[auth]>=1.66.0`.
5. In Streamlit Cloud app settings (or a local `.streamlit/secrets.toml` that
   is gitignored), add:

```toml
[auth]
redirect_uri = "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/oauth2callback"
cookie_secret = "generate-a-long-random-secret"
client_id = "your-google-oauth-client-id"
client_secret = "your-google-oauth-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

# Use each employee's exact time-sheet name and the Google account they will
# sign in with (company or personal). This may differ from the send-from
# mailbox. Leave a name out until you have the real address. Do not guess
# or commit real addresses.
[timesheet_employees]
# "Carl Mulvaney" = "their-signin-account@example.com"
# "Barry Markham" = "their-signin-account@example.com"
# "Robert Rackley" = "their-signin-account@example.com"
# "Gary Grant" = "their-signin-account@example.com"
# "Skylar Fingerle" = "their-signin-account@example.com"
# "Anthony Root" = "their-signin-account@example.com"
```

6. After deploy, the `redirect_uri` in secrets must match a URI registered on
   the Google client.

Time-sheet employees (Ron Cline has no timesheet):

- Carl Mulvaney
- Barry Markham
- Robert Rackley
- Gary Grant
- Skylar Fingerle
- Anthony Root (separate official form)

### Testing mode and verification (sign-in client)

Employee sign-in uses only OpenID email/profile scopes, which Google treats as
non-sensitive Sign in with Google scopes.

- While the OAuth consent screen is in **Testing**, only listed test users can
  sign in. Add each employee (and yourself) as a test user before they try.
- For those sign-in scopes, Google's 7-day refresh-token limit for Testing
  **does not apply** in the same way it does for Gmail scopes. Streamlit's
  identity cookie can last up to 30 days if the person does not sign out.
  Streamlit does not automatically expire that cookie from the ID token
  `exp` claim.
- When you are ready for everyone to use sign-in, set the consent screen to
  **Published**. Brand verification may still be required by Google for some
  public clients. This sign-in client should not request `gmail.send`.

## Mail send setup (later; not enabled now)

Use a **separate** Google OAuth client for Gmail send. Do not add send scopes
to the Streamlit sign-in client. Do not create a Microsoft mail-send client
for the current roster.

```toml
[timesheet_mail]
enabled = false
# Flip to true only after the callback host is deployed and the Gmail send
# client is registered.

[timesheet_mail.gmail]
client_id = "separate-gmail-send-client-id"
client_secret = "separate-gmail-send-client-secret"
redirect_uri = "https://YOUR-CALLBACK-HOST/timesheet-mail/callback/gmail"

[timesheet_mail_backend]
public_base_url = "https://YOUR-CALLBACK-HOST"
state_secret = "generate-a-long-random-secret"
app_base_url = "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/"

# Send-from mailbox and official provider. Leave empty until real values exist.
# For the current six, provider is one of: gmail, icloud, yahoo.
[timesheet_employee_mail]
# "Gary Grant" = { email = "their-gmail@example.com", provider = "gmail" }
# "Robert Rackley" = { email = "their-gmail@example.com", provider = "gmail" }
# "Anthony Root" = { email = "their-gmail@example.com", provider = "gmail" }
# "Carl Mulvaney" = { email = "their-icloud@example.com", provider = "icloud" }
# "Skylar Fingerle" = { email = "their-icloud@example.com", provider = "icloud" }
# "Barry Markham" = { email = "their-yahoo@example.com", provider = "yahoo" }

# Presence flag only for a vaulted SMTP store. Never put app-specific
# passwords in this file if it might be copied or logged. Use a real secret
# manager on the callback host.
# [timesheet_smtp]
# configured = false
```

Gmail send: POST `https://gmail.googleapis.com/gmail/v1/users/me/messages/send`
with a raw base64url MIME message. `gmail.send` is a sensitive scope; if you
later store refresh tokens in Testing mode they expire in 7 days. This
preparation prefers session-only access tokens (about one hour).

The authorized mailbox email from official userinfo must match the configured
employee send-from address. Access tokens stay in callback-host memory only.
HTTP 200 or 202 means the provider accepted the message, not proof of delivery.

### iCloud and Yahoo (SMTP vault; later)

If you enable those providers:

1. Each person generates an app-specific / app password on Apple or Yahoo
   account security (2FA required). Never collect those in chat or the app.
2. Store them only in a secret manager the callback host can read.
3. Set `[timesheet_smtp].configured = true` (or equivalent employee keys on
   the host) without putting the passwords in Streamlit forms or Sheets.
4. Sending remains off until that store is actually present.

Gmail employees can be enabled first, after the callback host and Gmail send
client exist, without waiting for the iCloud/Yahoo vault.

## Send rules

- Recipient is fixed: `patti@centralvalleyheli.com`. It cannot be edited.
- The person must be the signed-in employee, with initials that still match
  the current week content, and must attach the official generated PDF only.
- Duplicate send of the same employee + week + content hash already marked
  Sent is blocked.
- Uncertain results (timeout or 5xx) are not auto-retried. The person must
  check their Sent folder and explicitly acknowledge before trying again.
- 401 or 403 drops consent so they can authorize again.
- Errors are sanitized so tokens and secrets are not shown.

## Hard limitations

- In-app send is not available on Streamlit Community Cloud alone. A separate
  HTTPS callback service is required for Gmail OAuth send.
- iCloud has no public OAuth send API; Yahoo mail-w OAuth is not self-serve.
  Those stay fail-closed until a vaulted SMTP path exists.
- `mailto:`, Gmail compose URLs, and Outlook compose URLs cannot attach the
  generated PDF (RFC 6068). They are not used as fulfillment.
- Unmapped, unverified, or someone else's sign-in account cannot open a
  time sheet or send once `[auth]` is configured.
- Stale initials cannot send. Until `[auth]`, `[timesheet_mail].enabled`,
  the Gmail client, and the backend (and, for iCloud/Yahoo, the SMTP vault)
  are configured, the Email button stays disabled.

## What remains

Do not create a billing account, Cloud Run service, OAuth client, or secret,
and do not send a test timesheet, until that step is explicitly approved.

1. **Decide the callback host** (the next concrete choice): approve Google
   Cloud Run in the same project as the (not-yet-created) Google OAuth
   clients, accepting that a billing account / payment method is required
   even if expected Cloud Run cost is $0 under the official Free Tier; or
   say you do not want a Google billing account, and a Cloudflare Workers
   port can be prepared instead ($0/month, with the Free-plan CPU limit
   noted above).
2. After that host exists: create the Google OAuth web client for sign-in
   (no Gmail scopes) and a **separate** Gmail send client whose redirect URI
   is only on the callback host. Put `[auth]`, `[timesheet_employees]`,
   `[timesheet_employee_mail]`, and `[timesheet_mail_backend]` in Streamlit
   Cloud secrets. Do not commit them.
3. Add test users, try sign-in on the live app, then publish the consent
   screen when ready.
4. For iCloud and Yahoo send, vault app-specific passwords on that host
   later. Flip `[timesheet_mail].enabled` only after the relevant path is
   actually configured.
5. Do not enable production sending, grant live mail consent, or send a test
   timesheet until you explicitly approve that later step.
