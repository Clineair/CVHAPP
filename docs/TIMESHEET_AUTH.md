# Time-sheet sign-in and email

This document is the configuration and limitation guide for weekly time-sheet
access and direct in-app sending. Do not commit secrets, mailbox addresses, or
mail credentials. Sending stays off until the items below are all in place.

The app does not send mail until `[timesheet_company_mail].enabled` is true.
Every timesheet is sent from one company mailbox, `cvh@centralvalleyheli.com`,
to `patti@centralvalleyheli.com` (or `[timesheet_mail].recipient` when that
secret is set). Employees only enter a PIN. They do not authorize Google and
they do not use personal app passwords. The old Cloud Run callback is not on
this path and can be shut down.

## Opening a time sheet (employee PIN)

Employees do not sign in with Google to open a time sheet. They enter a PIN
once on that phone. The app stores an HMAC-signed cookie (`cvh_timesheet_device`)
for six years, using `[timesheet_pin].cookie_secret`. The cookie names the
employee. It does not contain the PIN. A remembered phone can see and send
only that employee's time sheet. **Not you? Switch employee** clears the cookie.

Chrome caps how long a browser will keep a cookie (about 400 days). Each visit
at least 30 days after the cookie was issued refreshes it, so a phone that
opens the app at least once a year stays remembered. Clearing site data, or
Switch employee, forgets the phone. Changing a PIN hash does not sign out
phones that are already remembered. Rotating `cookie_secret` does.

The Employees list and the calendar stay open with no PIN. Ron Cline has no
time sheet and no PIN.

If `[timesheet_pins]` or `[timesheet_pin].cookie_secret` is missing, the time
sheet shows **PIN not set up yet - ask the office** and does not crash.
A leftover `[auth]` block is ignored. The app does not call `st.login`.

Generate hashes with `python tools/make_pin_hash.py --employee "Carl Mulvaney"`
(type the PIN at the prompt). Placeholders are in `secrets.example.toml`.
Keys, same names as `[timesheet_employees]` and `[timesheet_employee_mail]`:

- `[timesheet_pin]` `cookie_secret`
- `[timesheet_pins]` `Carl Mulvaney`, `Anthony Root`, `Barry Markham`,
  `Robert Rackley`, `Gary Grant`, `Skylar Fingerle`

Five wrong PINs in one visit lock that visit. Close the page and open it
again to try again. The lock is not shared across phones.

## Sending from the company mailbox

The Send button runs in the Streamlit app. From is
`cvh@centralvalleyheli.com`, shown as `<Employee Name> via CVH Timesheets`.
Reply-To is the employee's address from `[timesheet_employee_mail]` when that
email exists, otherwise from `[timesheet_employees]`. Subject and body include
the employee name and the week. The attachment is the same generated PDF.
Initials must match the current week, and the employee must press Send.

If `[timesheet_company_mail]` is missing or `enabled` is not true, the sheet
shows **email not set up yet - ask the office**.

`backend` is `smtp` or `graph`.

- `smtp`: `smtp.office365.com` port 587 with STARTTLS. `username` is
  `cvh@centralvalleyheli.com`. `password` is that mailbox password or an app
  password. Microsoft 365 must have SMTP AUTH enabled for that mailbox.
- `graph`: client-credentials token, then
  `POST /users/cvh@centralvalleyheli.com/sendMail`. Keys are `tenant_id`,
  `client_id`, and `client_secret`. The Entra app needs the application
  permission `Mail.Send`, admin consent, and an application access policy
  that limits the app to that mailbox.

Placeholders are in `secrets.example.toml`. Do not commit the password or the
client secret.

## Implemented vs still a placeholder

**Implemented in this branch, but live sending stays off:**

- Time-sheet access for all six employees who have a form: the five official
  weekly forms, and Anthony Root's separate official form. Ron Cline has no
  time sheet.
- Official weekly mileage uses the IRS business rate that applies to the
  actual travel date, including a week that spans a rate change. Historic
  saved amounts are left alone. Anthony's form has no mileage fields.
- Preview of To, From, subject, body, and the official generated PDF, then an
  explicit Send button. Send posts that same PDF to the callback service.
  Mailto is not used as fulfillment.
- The recipient is `[timesheet_mail].recipient` when that secret is set.
  If it is absent, the long-standing fixed recipient remains the only allowed
  To. Initials must still match the current week content.
- Mail audit rows and a durable employee + week + content-hash claim both
  feed the send gate. A duplicate Sent claim is blocked. A timeout or 5xx is
  Uncertain and is not retried unless the employee explicitly confirms they
  checked Sent.
- Employee PIN plus a long-lived HMAC device cookie for opening a time sheet.
  Google sign-in (`st.login` / `[auth]`) is not used for access. A leftover
  `[auth]` section does not have to be removed. Gmail send is still a separate
  `gmail.send` consent on the callback host.
- Official Gmail send path (Gmail API `gmail.send`, authorization-code +
  PKCE, expiring single-use HMAC state, mailbox email from official userinfo
  must match the configured send-from address).
- Authenticated `POST /timesheet-mail/redeem` and `POST /timesheet-mail/send`.
  Streamlit signs a short-lived HMAC. The callback redeems the ready ticket
  into consent metadata only. The access token stays in the shared store.
  The public OAuth start and callback routes cannot send mail.
- Shared token store: `FirestoreMailTokenStore` for Cloud Run, with
  `MemoryMailTokenStore` kept as the test double and an explicit local
  override. Pending PKCE state, access tokens, tickets, API nonces, and
  idempotency claims expire and survive a process restart only in Firestore.
- iCloud SMTP (`smtp.mail.me.com:587` STARTTLS) and Yahoo SMTP
  (`smtp.mail.yahoo.com:587` STARTTLS or `:465` SSL). The Cloud Run service
  account reads each app-specific password from Secret Manager at send time.
  There is no password form in the app. Microsoft Graph send remains in the
  code and is dormant for the current roster.
- A non-root Dockerfile under `deploy/timesheet-mail-callback/`. It installs
  the callback dependencies and does not bake a serve override or secrets.
  Documented Cloud Run bounds are min instances 0 and max instances 2.

**Still external setup (do not treat the feature as turned on):**

- No callback host is deployed. No OAuth clients, Streamlit secrets, mailbox
  maps, Firestore database, or Secret Manager versions have been created.
- `[timesheet_mail].enabled` stays false until the steps below are done.
  `timesheet_email_can_send` stays false until that flag, the backend, a
  mail client or SMTP vault, identity, initials, the previewed PDF, and the
  fixed recipient are all present.
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
open a time sheet or to send. Opening the sheet is the PIN cookie. Sending
still uses the mailbox in `[timesheet_employee_mail]`.

iCloud and Yahoo employees send through the vaulted app-password path. Gmail
employees (Robert Rackley, Gary Grant, Anthony Root) authorize `gmail.send`
on the existing callback. The signed request names the PIN-verified employee
key. It does not embed `st.user`.

Gmail uses `access_type=online` and `prompt=consent`. No refresh token is
stored. The access token lives only in the callback store for about an hour.
The Google consent screen appears each time they authorize, which is when
that token is missing or expired, not on every Send while it is still valid.

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
# Flip to true only after the callback host is deployed, the Gmail send
# client is registered, and any iCloud or Yahoo secret versions exist.
recipient = "the-fixed-patti-address"

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

# Presence flag only. Never put app-specific passwords in this file.
# The callback reads passwords from Secret Manager, not from this section.
[timesheet_smtp]
configured = false
project = "YOUR-GCP-PROJECT"
# yahoo_port = 587
```

Gmail send: POST `https://gmail.googleapis.com/gmail/v1/users/me/messages/send`
with a raw base64url MIME message. `gmail.send` is a sensitive scope; if you
later store refresh tokens in Testing mode they expire in 7 days. This
preparation prefers session-only access tokens (about one hour).

The authorized mailbox email from official userinfo must match the configured
employee send-from address. Access tokens stay in the shared Firestore store
on the callback host. Streamlit receives consent metadata from
`POST /timesheet-mail/redeem` and never copies the access token into the
session, Sheets, or the query string. The ready redirect still carries only
the one-time opaque ticket.
HTTP 200 or 202 means the provider accepted the message, not proof of delivery.

### iCloud and Yahoo (Secret Manager)

The callback sends with TLS SMTP. iCloud uses `smtp.mail.me.com:587` with
STARTTLS. Yahoo uses `smtp.mail.yahoo.com:587` with STARTTLS, or port 465
with SSL when `[timesheet_smtp].yahoo_port` is `465`. It does not try the
other port after a failure, because that could send twice.

There is no password form. An admin creates these Secret Manager versions
later and pastes the app-specific password there:

- `timesheet-smtp-carl-mulvaney`
- `timesheet-smtp-skylar-fingerle`
- `timesheet-smtp-barry-markham`

The id is `timesheet-smtp-` plus the employee name in lowercase with spaces
as hyphens. It does not contain the mailbox address. The Cloud Run service
account needs `secretmanager.secretAccessor` on those secrets. Gmail
employees do not need an SMTP secret.

1. Each person generates an app-specific / app password on Apple or Yahoo
   account security (2FA required). Never collect those in chat or the app.
2. An admin pastes each value into Secret Manager. The app cannot do that.
3. Set `[timesheet_smtp].configured = true` and `project` to the GCP project
   id. Do not put the passwords in Streamlit secrets or Sheets.
4. Sending for that employee stays off until the secret version exists.
   A missing or revoked secret is a denial, not an automatic retry.

Gmail employees can be enabled first, after the callback host and Gmail send
client exist, without waiting for the iCloud/Yahoo secrets.

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
- A phone remembered for someone else cannot open or send another employee's
  time sheet. Without `[timesheet_pins]`, the sheet stays closed and shows
  the office message.
- Stale initials cannot send. Until `[timesheet_mail].enabled`,
  the Gmail client, and the backend (and, for iCloud/Yahoo, the SMTP vault)
  are configured, the Email button stays disabled. `[auth]` is not required.

## What remains

Nothing below has been done. Do not create a billing account, Cloud Run
service, OAuth client, or secret, and do not send a test timesheet, until
that step is explicitly approved. `[timesheet_mail].enabled` stays false
until you finish the relevant path and flip it yourself.

1. Create a Google Cloud project and attach a billing account. Billing is
   required even when Cloud Run stays inside the Free Tier. Enable Cloud
   Run, Firestore, and Secret Manager. Create a Firestore Native database.
   Expected Cloud Run cost at this volume is $0/month after the free amounts
   listed above; a payment method is still required, and overage is billed.
2. Deploy `deploy/timesheet-mail-callback/Dockerfile` to Cloud Run in
   us-central1 with `--min-instances=0 --max-instances=2 --port=8080
   --timeout=60 --concurrency=20 --allow-unauthenticated`. The browser has
   to reach the OAuth redirect. Send and redeem stay HMAC-authenticated.
   Give the runtime service account Cloud Datastore User and Secret Manager
   Secret Accessor. Set `GOOGLE_CLOUD_PROJECT` and
   `TIMESHEET_MAIL_TOKEN_STORE=firestore`. Mount the same mail configuration
   JSON as `TIMESHEET_MAIL_SECRETS_JSON` from Secret Manager. Do not put
   SMTP passwords in that JSON.
3. Optional but recommended: a Firestore TTL policy on collection
   `timesheet_mail_tokens`, field `expire_at`. Reads already ignore expired
   documents if the policy is not created yet.
4. Create two OAuth web clients in that project. Do not combine them.
   - Sign-in client: scopes `openid`, `profile`, and `email` only. Redirects:
     `http://localhost:8501/oauth2callback` and
     `https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/oauth2callback`.
   - Gmail send client: scope `https://www.googleapis.com/auth/gmail.send`
     only. Redirect only
     `https://YOUR-CALLBACK-HOST/timesheet-mail/callback/gmail`.
   Leave the consent screen in Testing and add the employees as test users
   before anyone tries. Publish it only when you want everyone to use it.
   Do not register a Microsoft mail-send client for the current roster.
5. In Streamlit secrets, not in git, set `[auth]` for the sign-in client,
   `[timesheet_employees]` to each person's Google sign-in address,
   `[timesheet_employee_mail]` to the send-from mailbox and provider
   (`gmail`, `icloud`, or `yahoo`), `[timesheet_mail].enabled = false`,
   `[timesheet_mail].recipient` to Patti's address, `[timesheet_mail.gmail]`
   to the send client, and `[timesheet_mail_backend]` with `public_base_url`,
   the same `state_secret` the callback has, and `app_base_url`.
6. For Carl, Skylar, and Barry, generate Apple or Yahoo app-specific
   passwords outside this app. An admin pastes them into Secret Manager
   under the ids above. Then set `[timesheet_smtp].configured = true` and
   `project` to the GCP project. Gmail employees can be turned on without
   those three secrets.
7. Put the same non-password configuration on the callback
   (`TIMESHEET_MAIL_SECRETS_JSON`), including `timesheet_employee_mail`,
   the Gmail send client, `state_secret`, and `recipient`. The HMAC request
   carries `employee_key` (the PIN-verified employee name). HMAC validation
   still uses `state_secret`. The Gmail userinfo address must match that
   employee's send-from mailbox. A callback image from before the PIN change
   still requires `signin_email` to map through `[timesheet_employees]` and
   will deny `employee_key`-only requests until that image is redeployed.
   Do not deploy that change until it is explicitly approved.
8. Confirm a timesheet still saves, the Email button stays disabled while
   `enabled` is false, then set `enabled = true`. Each employee enters their
   PIN once, initials the current week, previews the PDF, authorizes Gmail
   send or waits for the vaulted SMTP session, and presses Send. The first
   unclear result must be checked in the sender's Sent folder before anyone
   sends that same week again.
9. Do not merge this PR, enable production sending, grant live mail consent,
   or send a test timesheet until you explicitly approve that later step.
