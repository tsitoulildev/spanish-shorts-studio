"""Upload one rendered ambient video to YouTube (resumable). Credentials only from env: AMBIENT_YT_CLIENT_ID/SECRET/REFRESH_TOKEN.
The video is uploaded private; privacy comes from AMBIENT_YT_PRIVACY (default private)."""
from __future__ import annotations
import json, os, sys
import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def creds():
    v = [os.environ.get(k, "").strip() for k in ("AMBIENT_YT_CLIENT_ID", "AMBIENT_YT_CLIENT_SECRET", "AMBIENT_YT_REFRESH_TOKEN")]
    return v if all(v) else None


def upload(video: str, p: dict, privacy: str) -> str:
    c = creds()
    r = requests.post(TOKEN_URL, data={"client_id": c[0], "client_secret": c[1], "refresh_token": c[2], "grant_type": "refresh_token"}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"token refresh failed: HTTP {r.status_code}")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    meta = {"snippet": {"title": p["title"][:100], "description": p["description"], "tags": p["tags"], "categoryId": "10"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    size = os.path.getsize(video)
    init = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, json=meta, timeout=60,
                         headers={**h, "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    if init.status_code != 200 or not init.headers.get("Location"):
        raise SystemExit(f"upload start refused: HTTP {init.status_code} {init.text[:300]}")
    with open(video, "rb") as fh:
        put = requests.put(init.headers["Location"], data=fh, timeout=7200, headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    if put.status_code not in (200, 201):
        raise SystemExit(f"upload failed: HTTP {put.status_code} {put.text[:300]}")
    return put.json()["id"]


if __name__ == "__main__":
    plan = json.loads(sys.argv[2])
    print(upload(sys.argv[1], plan, os.environ.get("AMBIENT_YT_PRIVACY", "private") or "private"))
