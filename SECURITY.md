# Security policy

## Reporting a problem
Please report security issues privately, not in a public issue: use GitHub's **Security > Report a vulnerability** (private vulnerability reporting) on this repository. If that option is not visible, open a public issue that says only "security contact needed", without any details, and a maintainer will reply with a private channel.

Relevant reports include: a secret, token or key committed anywhere in the repository, a workflow that exposes a secret or runs untrusted code with secrets, and a dependency or supply-chain risk in the build.

## What this project does to stay safe
- No keys, tokens or credentials are stored in the repository. YouTube credentials exist only as GitHub Actions secrets (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`) and are read from environment variables. Error messages never print them.
- Workflows never use `pull_request_target`, never use self-hosted runners, and do not run on pull requests from forks with secrets. The upload workflow runs only on a push to `main`, i.e. after a lesson has been merged by a maintainer, and uploads each lesson at most once (ledger).
- The OAuth scope used for upload is `youtube.upload`, which cannot read or delete anything on the channel.
- User-controlled workflow inputs are passed through environment variables and validated, never interpolated into shell commands.

## If a secret is ever exposed
Revoke or rotate it at the provider first (Google Cloud console for the YouTube client and refresh token, GitHub for tokens), then remove it from the repository. Rewriting history alone does not make a leaked secret safe.

## Supported versions
Only the latest commit on `main`.

## Recommended repository settings
Require a pull request before merging into `main` (this is what makes a merge an approval), enable private vulnerability reporting, and keep Actions secrets limited to the three names above.
