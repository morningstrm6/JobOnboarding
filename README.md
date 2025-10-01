# HR Onboarding Bot

This repository contains a Telegram HR onboarding bot that collects employee details and writes them to a Google Sheet.

## Files included
- `.github/workflows/python-package.yml` - CI for linting and tests
- `.github/workflows/deploy.yml` - Build & push Docker image (push to DockerHub if secrets set)
- `Dockerfile` - container image
- `requirements.txt` - Python deps
- `bot.py` - Main bot file (webhook mode)
- `README.md` - this file

## Required environment variables (for runtime)
- `BOT_TOKEN` - Telegram bot token
- `SPREADSHEET_ID` - Google sheet ID (the spreadsheet must be shared with service account)
- `GOOGLE_CREDS_JSON_CONTENT` - Full content of service account JSON (as string)
- `APP_URL` - Public HTTPS URL where Telegram will send webhooks (e.g. https://example.com)

Optional:
- `HR_TELEGRAM_USERNAME` - e.g. hr_team
- `ONBOARDING_IMAGE_URL` - image to send upon completion
- `PORT` - port to listen on (default 8080)

## Notes on deployment to Choreo
Choreo-specific deployment typically requires uploading source or a container image via the Choreo console or CLI.
This repo's `deploy.yml` builds a Docker image and can push to DockerHub if you set the following secrets in GitHub:
- `DOCKER_USERNAME`
- `DOCKER_PASSWORD`
- `IMAGE_NAME` - The full name of the image for DockerHub (e.g., `your-username/hr-onboarding`).
 
### Obtaining Docker Hub Credentials
To enable the workflow to push to Docker Hub, you need to provide credentials.

1.  **Sign up for Docker Hub**: If you don't have one, create a free account at hub.docker.com. Your `DOCKER_USERNAME` is your  Docker ID.
2.  **Create an Access Token**:
    - In Docker Hub, go to **Account Settings > Security**.
    - Click **New Access Token**.
    - Give it a name (e.g., `github-actions-bot`) and set permissions to `Read, Write, Delete`.
    - Copy the generated token. This will be your `DOCKER_PASSWORD` secret. 
3.  **Define your Image Name**: The `IMAGE_NAME` should follow the format `your-docker-id/repository-name`,  for example: `johndoe/hr-onboarding-bot`.
4.  **Add to GitHub Secrets**:
    - In your GitHub repository, go to `Settings` > `Secrets and variables` > `Actions`.
    - Click `New repository secret` for each of the three values (`DOCKER_USERNAME`, `DOCKER_PASSWORD`, `IMAGE_NAME`).
 
After the image is pushed, log in to the Choreo console and deploy the image (or upload source). Automating Choreo deploy via Actions requires Choreo-specific credentials and API/CLI which vary by account; follow your Choreo docs.

## Local testing
For quick local testing you can switch the run mode to polling by replacing the `app.run_webhook(...)` line in `bot.py` with `app.run_polling()` and running:

```bash
export BOT_TOKEN="your-token"
export SPREADSHEET_ID="your-sheet-id"
export GOOGLE_CREDS_JSON_CONTENT="$(cat service-account.json | jq -c .)"
export APP_URL="https://example.com"  # not used in polling
python bot.py
```
