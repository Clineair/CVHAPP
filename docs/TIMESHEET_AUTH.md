# Time-sheet sign-in and email

This document is the configuration and limitation guide for weekly time-sheet
access and direct in-app sending. Do not commit secrets, mailbox addresses, or
mail credentials. Sending stays off until the items below are all in place.

The app does not send mail in the current default configuration. There is no
Ron or shared mailbox sender. Each employee must send from their own authorized
mailbox, only to `patti@centralvalleyheli.com`, only after they review and
explicitly press Send.

## Architectural decision: Streamlit Cloud cannot host the mail OAuth callback

Streamlit Community Cloud reserves `/oauth2callback` for `st.login()`. The app
cannot also receive a provider `form_post` response, and using the Streamlit
app URL as a second OAuth redirect would put an authorization code in the
browser query string and history, which this project forbids.

A second, separate HTTPS callback service is therefore a hard prerequisite for
Gmail and Microsoft Graph sending. The Streamlit app never exchanges the
authorization code, never stores refresh tokens, and never puts access tokens
in query parameters, Sheets, the repo, logs, or another employee's session.
`timesheet_mail_callback.py` is a scaffold only; it is not started by the
Streamlit app and is not a production host by itself. Until that service is
deployed and `[timesheet_mail].enabled`, mail client keys, and
`[timesheet_mail_backend]` are all present, `timesheet_email_can_send` stays
False.

Signing in with Google OpenID does not grant permission to send mail. Mail
send uses a separate, least-privilege consent (`gmail.send` or Microsoft
`Mail.Send`) and a short-lived access token when the official OAuth path
applies.

## Official provider support

Employee send-from addresses are not stored in the repo. Configure them later
only in Streamlit / backend secrets. Do not invent addresses.

| Provider | Official send method | Prerequisite |
| --- | --- | --- |
| Gmail | OAuth 2.0 + Gmail API `gmail.send` (session-only access token; `access_type=online`) | Separate callback host, Google mail OAuth client, employee mailbox mapping |
| Microsoft 365, Outlook.com, Hotmail, Live.com | OAuth 2.0 + Microsoft Graph `Mail.Send` (work or personal; tenant `common` or `consumers`) | Separate callback host, Microsoft mail OAuth client, employee mailbox mapping |
| iCloud Mail | **SMTP only** (`smtp.mail.me.com:587`, STARTTLS). Apple publishes no public OAuth or REST send API for third-party apps. Username is the full iCloud address. Password must be an [app-specific password](https://support.apple.com/en-us/102654) from account.apple.com (2FA required), never the Apple Account password. See [Apple Mail server settings](https://support.apple.com/en-us/102525). | Secure backend/vault to hold the app-specific password. Fail closed until that vault exists. |
| Yahoo Mail | **SMTP** (`smtp.mail.yahoo.com:587` or `465`) with a [Yahoo app password](https://help.yahoo.com/kb/mail/generate-password-sln15241.html). Yahoo IMAP/SMTP OAuth (`mail-w`) exists only after a commercial access application; it is not self-serve in the developer console. Sign in with Yahoo is login only, not mail send. | Secure backend/vault to hold the app password, or approved Yahoo commercial OAuth later. Fail closed until that exists. |
| Other personal providers | Not claimed. There is no generic SMTP form in the app. | Do not add a password field to Streamlit or Sheets. |

App-specific passwords are long-lived secrets, which is a substantially
different architecture from session-only OAuth. This app will never ask an
employee for a mail password in chat or a form, and it will never store mail
credentials in Google Sheets or in a downloaded timesheet. Provision those
secrets later only into a secure backend or vault if you choose to enable
iCloud or Yahoo sending.

The product is not limited to Gmail and Microsoft. iCloud and Yahoo are
recognized providers, but sending for those mailboxes stays off until the
vaulted SMTP path is actually configured. Do not treat a `mailto:` helper as
fulfillment of in-app send.

## What shipped in the app

- **Employee sign-in** uses Streamlit's documented Google OpenID Connect flow
  (`st.login()` / `st.user` / `st.logout()`, callback path `/oauth2callback`).
  See [Use the Google Auth Platform to authenticate users](https://docs.streamlit.io/develop/tutorials/authentication/google)
  and [st.login](https://docs.streamlit.io/develop/api-reference/user/st.login).
- **Identity mapping** is configuration-only: a verified Google email (issuer
  `https://accounts.google.com`, `email_verified` true) is mapped to one exact
  time-sheet employee name. The employee cannot pick a name, and an arbitrary
  email domain is not trusted by itself. The sign-in address may differ from
  the send-from mailbox.
- **Employee emails are not stored in the repo.** `[timesheet_employees]`
  (sign-in) and `[timesheet_employee_mail]` (send-from address + provider)
  stay empty until you add real values in secrets. Until then, once `[auth]`
  is present, time sheets fail closed. Duplicate mapped emails also fail closed.
- **Protection is limited to time sheets.** FRAT, equipment, calendar, and
  other header pages stay usable without signing in. When auth is configured,
  a person can still open another employee *page*, but that person's time-sheet
  form and records are not shown or loaded.
- **If `[auth]` is not configured**, time-sheet fill / save / download stay as
  they are today, and email stays disabled. That open access is the current
  default; it is not weakened, and it is not treated as signed-in email.
- **In-app sending is prepared but disabled.** Preview shows To, From, subject,
  body, and the official generated PDF attachment name. The Send button stays
  disabled until secure setup, identity, initials, consent, and the PDF are
  all valid. No automatic or routine sends.

## Streamlit Cloud / local sign-in setup

Do this in Google Cloud and Streamlit secrets. Do not paste client secrets into
the repo, chat, or logs.

1. In a Google Cloud project, configure the Google Auth Platform branding and
   audience as described in the Streamlit Google tutorial above.
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
# sign in with (company or personal). Leave a name out until you have the
# real address. Do not guess.
[timesheet_employees]
# "Carl Mulvaney" = "their-google-account@example.com"
# "Barry Markham" = "their-google-account@example.com"
# "Robert Rackley" = "their-google-account@example.com"
# "Gary Grant" = "their-google-account@example.com"
# "Skylar Fingerle" = "their-google-account@example.com"
```

6. After deploy, the `redirect_uri` in secrets must match a URI registered on
   the Google client.

Time-sheet employees on the official weekly form (Ron Cline has no timesheet;
Anthony Root is not on this email-preparation change):

- Carl Mulvaney
- Barry Markham
- Robert Rackley
- Gary Grant
- Skylar Fingerle

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

Use a **separate** Google OAuth client and a **separate** Microsoft app for
mail send. Do not add send scopes to the Streamlit sign-in client.

```toml
[timesheet_mail]
enabled = false
# Flip to true only after the callback host is deployed and clients are registered.

[timesheet_mail.gmail]
client_id = "separate-gmail-send-client-id"
client_secret = "separate-gmail-send-client-secret"
redirect_uri = "https://YOUR-CALLBACK-HOST/timesheet-mail/callback/gmail"

[timesheet_mail.microsoft]
client_id = "separate-microsoft-send-client-id"
client_secret = "separate-microsoft-send-client-secret"
redirect_uri = "https://YOUR-CALLBACK-HOST/timesheet-mail/callback/microsoft"
tenant = "common"

[timesheet_mail_backend]
public_base_url = "https://YOUR-CALLBACK-HOST"
state_secret = "generate-a-long-random-secret"
app_base_url = "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/"

# Send-from mailbox and official provider. Leave empty until real values exist.
# provider must be one of: gmail, microsoft, icloud, yahoo.
[timesheet_employee_mail]
# "Gary Grant" = { email = "their-gmail@example.com", provider = "gmail" }
# "Robert Rackley" = { email = "their-hotmail@example.com", provider = "microsoft" }
# "Carl Mulvaney" = { email = "their-icloud@example.com", provider = "icloud" }
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

Microsoft send: POST `https://graph.microsoft.com/v1.0/me/sendMail` with a
file attachment. HTTP 200 or 202 from Gmail or Graph means the provider
accepted the message, not proof of delivery.

The authorized mailbox email from official userinfo must match the configured
employee send-from address. Access tokens stay in callback-host memory only.

### iCloud and Yahoo (SMTP vault; later)

If you enable those providers:

1. Each person generates an app-specific / app password on Apple or Yahoo
   account security (2FA required). Never collect those in chat or the app.
2. Store them only in a secret manager the callback host can read.
3. Set `[timesheet_smtp].configured = true` (or equivalent employee keys on
   the host) without putting the passwords in Streamlit forms or Sheets.
4. Sending remains off until that store is actually present.

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
  HTTPS callback service is required for Gmail and Microsoft OAuth send.
- iCloud has no public OAuth send API; Yahoo mail-w OAuth is not self-serve.
  Those two stay fail-closed until a vaulted SMTP path exists.
- `mailto:`, Gmail compose URLs, and Outlook compose URLs cannot attach the
  generated PDF (RFC 6068). They are not used as fulfillment.
- Unmapped, unverified, or someone else's Google account cannot open a
  time sheet or send once `[auth]` is configured.
- Stale initials cannot send. Until `[auth]`, `[timesheet_mail].enabled`,
  clients, and the backend (and, for iCloud/Yahoo, the SMTP vault) are
  configured, the Email button stays disabled.

## What remains for you

1. Create the Google OAuth web client for sign-in (no Gmail scopes) and put
   `[auth]` plus each real `[timesheet_employees]` address in Streamlit Cloud
   secrets. Do not commit them.
2. Add test users, try sign-in on the live app, then publish the consent
   screen when ready.
3. Deploy a separate HTTPS callback host from `timesheet_mail_callback.py`
   (production hardening is still required) and register separate Gmail and
   Microsoft mail-send clients, with redirect URIs on that host only.
4. Put `[timesheet_employee_mail]` provider mappings and, if you choose to
   support iCloud or Yahoo, vaulted app-specific passwords on that host.
   Flip `[timesheet_mail].enabled` only after that is done.
5. Do not enable production sending, grant live OAuth consent, or send a test
   timesheet until you explicitly approve that later step.
