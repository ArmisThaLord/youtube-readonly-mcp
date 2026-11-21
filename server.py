"""Single-owner, read-only YouTube MCP server."""
import hmac
import os
import re
from datetime import date
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import PlainTextResponse

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]
DEFAULT_METRICS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained"

def _csv(name, default=""):
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]

mcp = FastMCP(
    "youtube-readonly", stateless_http=True, json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=_csv("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*"),
        allowed_origins=_csv("MCP_ALLOWED_ORIGINS")))

def service(name, version):
    path = Path(os.getenv("GOOGLE_TOKEN_FILE", "token.json"))
    if not path.is_file():
        raise ValueError("Google authorization is not configured. Run auth_setup.py on your own computer.")
    credentials = Credentials.from_authorized_user_file(str(path), SCOPES)
    return build(name, version, credentials=credentials, cache_discovery=False)

def execute(request):
    try:
        return request.execute()
    except HttpError as exc:
        # Do not expose request URLs, authorization headers, or response details.
        raise RuntimeError(f"Google API request failed (HTTP {exc.resp.status}). Check API access, consent, limits and server logs.") from None

def valid_dates(start_date, end_date):
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError:
        raise ValueError("Dates must be YYYY-MM-DD.") from None
    if start > end or end > date.today():
        raise ValueError("Start must not be after end, and end must not be in the future.")

def valid_video(video_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Invalid YouTube video ID.")

@mcp.tool()
def channel_info() -> dict:
    """Get the authorized account's channel metadata, statistics and uploads playlist."""
    yt = service("youtube", "v3")
    result = execute(yt.channels().list(part="snippet,statistics,contentDetails", mine=True, maxResults=50))
    return {"items": result.get("items", [])}

@mcp.tool()
def list_uploads(max_results: int = 25, page_token: str = "") -> dict:
    """List the authorized channel's uploads with metadata. Use nextPageToken to paginate."""
    if not 1 <= max_results <= 50: raise ValueError("max_results must be between 1 and 50.")
    yt = service("youtube", "v3")
    channels = execute(yt.channels().list(part="contentDetails", mine=True, maxResults=1)).get("items", [])
    if not channels: return {"items": [], "message": "No YouTube channel found for this account."}
    playlist = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    args = dict(part="snippet,contentDetails", playlistId=playlist, maxResults=max_results)
    if page_token: args["pageToken"] = page_token
    return execute(yt.playlistItems().list(**args))

@mcp.tool()
def video_details(video_ids: list[str]) -> dict:
    """Get metadata and public statistics for 1 to 50 video IDs."""
    if not 1 <= len(video_ids) <= 50: raise ValueError("Provide 1 to 50 video IDs.")
    for video_id in video_ids: valid_video(video_id)
    return execute(service("youtube", "v3").videos().list(part="snippet,statistics,contentDetails", id=",".join(video_ids), maxResults=50))

@mcp.tool()
def channel_analytics(start_date: str, end_date: str, group_by: Literal["day", "video"] = "video", max_results: int = 25) -> dict:
    """Get channel performance grouped by video or day. Dates are inclusive YYYY-MM-DD."""
    valid_dates(start_date, end_date)
    if not 1 <= max_results <= 200: raise ValueError("max_results must be 1 to 200.")
    if group_by not in ("day", "video"): raise ValueError("group_by must be day or video.")
    return execute(service("youtubeAnalytics", "v2").reports().query(
        ids="channel==MINE", startDate=start_date, endDate=end_date, dimensions=group_by,
        metrics=DEFAULT_METRICS, sort="-views" if group_by == "video" else "day", maxResults=max_results))

@mcp.tool()
def audience_retention(video_id: str, start_date: str, end_date: str) -> dict:
    """Get the relative-position audience retention curve for one owned video."""
    valid_video(video_id); valid_dates(start_date, end_date)
    return execute(service("youtubeAnalytics", "v2").reports().query(
        ids="channel==MINE", startDate=start_date, endDate=end_date,
        dimensions="elapsedVideoTimeRatio", metrics="audienceWatchRatio",
        filters=f"video=={video_id}"))

class BearerAuth:
    def __init__(self, app, token):
        self.app, self.token = app, token.encode()
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        values = [v for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
        expected = b"Bearer " + self.token
        if len(values) != 1 or not hmac.compare_digest(values[0], expected):
            response = PlainTextResponse("Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)

def create_app():
    token = os.getenv("MCP_BEARER_TOKEN", "")
    if len(token) < 32 or token == "replace-with-a-long-random-secret-at-least-32-characters" or not token.isascii() or any(c.isspace() for c in token):
        raise RuntimeError("Set a unique random ASCII MCP_BEARER_TOKEN of at least 32 characters, with no whitespace.")
    return BearerAuth(mcp.streamable_http_app(), token)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")), access_log=False)
