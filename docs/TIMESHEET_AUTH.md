# Time-sheet sign-in and email

This document is the configuration and limitation guide for weekly time-sheet
access and email. The app does not send mail itself. Do not commit secrets.

## What shipped in the app

- **Employee sign-in** uses Streamlit's documented Google OpenID Connect flow
  (`st.login()` / `st.user` / `st.logout()`, callback path `/oauth2callback`).
  See [Use the Google Auth Platform to authenticate users](https://docs.streamlit.io/develop/tutorials/authentication/google)
  and [st.login](https://docs.streamlit.io/develop/api-reference/user/st.login).
- **Identity mapping** is configuration-only: a verified Google email is mapped
  to one exact time-sheet employee name. The employee cannot pick a name, and
  an arbitrary email domain is not trusted by itself.
- **Employee emails are not stored in the repo.** The mapping stays empty until
  you add each person's real sign-in address in Streamlit secrets. Until then,
  once `[auth]` is present, time sheets fail closed (no one can open payroll).
- **Protection is limited to time sheets.** FRAT, equipment, calendar, and
  other header pages stay usable without signing in. When auth is configured,
  a person can still open another employee *page*, but that person's time-sheet
  form and records are not shown or loaded.
- **If `[auth]` is not configured**, time-sheet fill / save / download stay as
  they are today, and email stays disabled. That open access is the current
  default; it is not weakened, and it is not treated as signed-in email.
- **In-app sending is off.** There is no Ron/shared mailbox OAuth, no SMTP
  send, no public token endpoint, and no credential-input screen in the app.

## Recommended email workflow (own account)

Employees have their own company or personal email. The practical method that
works across unknown providers is:

1. Sign in with the Google account listed for you.
2. Complete the week, initial it, and save.
3. Download the official PDF.
4. Open a message that is already addressed to
   `patti@centralvalleyheli.com`, with a prepared subject and body.
5. Attach the downloaded PDF yourself in your email app, review it, and press
   Send there.

The app never claims that the PDF was attached or that the message was sent.
The From address is whatever account is set in the person's own email app,
which may differ from the Google account used to sign in.

### Options considered

| Method | Feasibility |
| --- | --- |
| `mailto:` to Patti with subject and body (RFC 6068) | Supported and provider-agnostic. **Cannot attach a file.** RFC 6068 has no attachment field; MIME headers in a mailto URI must be ignored. This is the recommended composer helper. |
| Gmail or Outlook web compose URLs | Also cannot attach a generated PDF through the URL. Opens one provider's web UI, not every employee's mail. Not used as the primary path. |
| Downloadable `.eml` with the PDF attached and `X-Unsent: 1` | Not a reliable draft. `X-Unsent` is an unofficial Outlook convention; it has broken in New Outlook at times. Microsoft's documented behavior is opening `.eml` as a message, not creating a draft in Gmail or every mail app. Not recommended. |
| Web Share API (`navigator.share({ files })`) | Support varies (commonly mobile; not Firefox desktop). It cannot target Patti or a specific mail app. Streamlit has no built-in file-share button. Not recommended as the primary path. |
| Per-user Gmail / Microsoft Graph OAuth in the app | Would be required for true in-app send and auto-attachment from each person's account. Needs approved account mapping and per-provider setup. **Not built unless you choose that later.** |
| Shared send-from-Ron Gmail | Not built. Employees send from their own accounts. |

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

Time-sheet employees (no timesheet for Ron Cline or Anthony Root):

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
- `gmail.send` is a **sensitive** scope. It is not used by this app. If you
  later ask for per-user or shared Gmail API sending, that would need a
  separate OAuth client, offline access, a refresh token stored only in
  Streamlit secrets, and usually sensitive-scope verification (including a
  demo video) to move out of Testing. In Testing, refresh tokens for
  sensitive scopes expire in **7 days**. Do not start that work unless you
  choose in-app sending later.

## Hard limitations

- The app cannot attach the generated PDF to mailto, Gmail compose, or Outlook
  compose URLs, and it cannot press Send in the employee's mailbox.
- The app cannot prove that a message was sent, and it will not auto-retry a
  mail failure it never caused.
- Unmapped, unverified, or someone else's Google account cannot open a
  time sheet or the composer once `[auth]` is configured.
- Stale initials (content changed after the last initialed save) cannot open
  the composer. The To address cannot be changed; only
  `patti@centralvalleyheli.com` is allowed.
- Until you add `[auth]` and the email map, time sheets remain editable
  without sign-in, and the Email button stays disabled.

## What remains for you

1. Create the Google OAuth web client for sign-in (no Gmail scopes).
2. Put `[auth]` and each real `[timesheet_employees]` address in Streamlit
   Cloud secrets. Do not commit them.
3. Add test users, try sign-in on the live app, then publish the consent
   screen when ready.
4. Tell employees to download the PDF, open the preaddressed message, attach
   the file, and send it from their own account.
5. Only if you later want the app to send and attach automatically, choose
   per-user provider OAuth (Gmail and/or Microsoft) with approved account
   mapping. That is a separate, larger setup.
