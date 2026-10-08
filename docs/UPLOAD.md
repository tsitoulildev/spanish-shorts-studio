# YouTube upload: approval becomes publication

## Flow
1. The writer opens a pull request for a lesson (docs/AUTOMATION.md). The human watches the video and **merges** = approval.
2. The merge triggers `.github/workflows/publish.yml`. It rebuilds that lesson (same voices, same QA gate) and runs `scriptstudio upload`.
3. `upload` refuses unless ALL gates pass: `check` has no BLOCK and no PUBLISH flag (Spanish reviewed), QA says PASS, the video is at most 40 s, the lesson id is not already in the ledger.
4. Title, description, tags and the "synthetic media" declaration are generated from the lesson file (`upload.build_metadata`). Nothing is typed by hand. The description lists every phrase with its pronunciation, the Argentine-Spanish note with the "tell us about a mistake" invitation, the synthetic-voice notice, the CC BY-SA voice credit from `credits.txt`, and hashtags.
5. The ledger (`ledger.json` on the branch `published`) records `lesson id -> video id`, so a re-run never uploads twice.

Until the three secrets below exist the workflow does a dry run: it prints exactly what it would send and uploads nothing. A manual run (Actions > Publish approved lessons > Run workflow, with a lesson id) republishes one lesson.

## Visibility: private first (a YouTube rule, not ours)
YouTube forces every video uploaded through the API from an **unverified** API project to `private`. So the upload creates a **private** video, and the human makes it **Public** (or schedules it) in YouTube Studio: one click, which is the second approval. To lift the restriction YouTube requires a compliance audit of the API project; apply for it only if the channel grows (the form is linked from the YouTube Data API documentation). The `YT_PRIVACY` repository variable (private, unlisted, public) is already honoured, so nothing changes in the code when the audit is granted.

## One-time setup (only a person can do this: it is the channel owner's Google account)
1. console.cloud.google.com: create a project, enable **YouTube Data API v3**.
2. OAuth consent screen: user type External, add yourself as a test user, then set the publishing status to **In production**. Reason: while the status is "Testing", Google expires the refresh token after 7 days and uploads would silently stop. An unverified app in production only shows a warning screen for your own account.
3. Credentials: create an **OAuth client ID** of type *Web application* with the redirect URI `https://developers.google.com/oauthplayground`.
4. Open developers.google.com/oauthplayground, click the gear, tick "Use your own OAuth credentials", paste the client ID and secret. In step 1 enter the scope `https://www.googleapis.com/auth/youtube.upload`, authorise with the channel's account, then in step 2 "Exchange authorization code for tokens". Copy the **refresh token**.
5. In the GitHub repo: Settings > Secrets and variables > Actions > new repository secrets `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. Never put them in a file, an issue or a chat.

The scope `youtube.upload` can only upload; it cannot read or delete anything on the channel.

## Rules built into the code
- Credentials are read only from environment variables; error messages report the HTTP status and Google's error code, never the request.
- `containsSyntheticMedia` is declared true by default, because the narration is text-to-speech. `selfDeclaredMadeForKids` is false (adult learners).
- Tests (`UploadTests`) run the whole flow against a fake HTTP layer: gates, ledger, dry run, token error.
- Quota: the default API quota allows several uploads per day; the plan is three per week.

## Not built (decisions for later)
- Scheduling (`publishAt`) and a pinned comment (the API cannot pin). The pinned-comment line is already in the description.
- Thumbnails (Shorts use a frame; optional later).
