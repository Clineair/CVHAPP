# Callback-only image. Build from the repository root:
#   docker build -f deploy/timesheet-mail-callback/Dockerfile -t timesheet-mail-callback .
# Do not deploy or provision a billed host until that step is explicitly approved.
#
# Runtime configuration comes from the environment and Secret Manager.
# Do not bake TIMESHEET_MAIL_ALLOW_SERVE, client secrets, or app passwords
# into this image. Cloud Run should use:
#   --min-instances=0 --max-instances=2 --port=8080 --timeout=60 --concurrency=20
#   --allow-unauthenticated
# The service is public so a browser can complete the OAuth redirect.
# POST /timesheet-mail/redeem, /smtp-session, and /send still require a
# short-lived HMAC from Streamlit. The OAuth routes cannot send mail.
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY deploy/timesheet-mail-callback/requirements.txt /tmp/callback-requirements.txt
RUN pip install --no-cache-dir -r /tmp/callback-requirements.txt \
    && rm -rf /root/.cache/pip

COPY timesheet_mail.py timesheet_mail_callback.py ./

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV TIMESHEET_MAIL_TOKEN_STORE=firestore

EXPOSE 8080
USER appuser

# The container command starts the server directly. This image does not set
# a serve override. Running the module as a script still refuses to serve.
CMD ["python", "-c", "import timesheet_mail_callback as callback; callback.serve()"]
