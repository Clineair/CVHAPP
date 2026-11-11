# Callback-only image. Build from the repository root:
#   docker build -f deploy/timesheet-mail-callback/Dockerfile -t timesheet-mail-callback .
# Do not deploy or provision a billed host until that step is explicitly approved.
FROM python:3.12-slim
WORKDIR /app
COPY timesheet_mail.py timesheet_mail_callback.py ./
ENV PORT=8080
ENV TIMESHEET_MAIL_ALLOW_SERVE=1
EXPOSE 8080
CMD ["python", "-u", "timesheet_mail_callback.py"]
