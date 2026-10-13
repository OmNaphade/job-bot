# Security

## Secrets

The Telegram bot token, the Gmail app password and any API keys live only in a local `.env` (git-ignored) and in
GitHub repository secrets. Nothing in the code logs them; Telegram errors are logged by exception type only
because the request URL contains the bot token.

If a secret leaks, rotate it: `/revoke` in @BotFather for the bot token, delete the app password at
myaccount.google.com/apppasswords, then update the repository secrets.

## Accounts on job sites

The bot never logs in to LinkedIn, Naukri, Foundit or Indeed. The only login is read-only IMAP access to the
alert mailbox, using an app password (revocable at any time, and not your Google password).

## Reporting a problem

Open a GitHub issue for ordinary bugs. For anything that involves a leaked credential, do not paste it in the
issue; rotate it first and describe what happened.
