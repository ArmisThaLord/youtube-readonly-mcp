# YouTube Read-only MCP

A single-owner Python starter that exposes YouTube uploads, channel details, video statistics, analytics and retention as read-only MCP tools. Google OAuth is required for the channel's private analytics. This is an independent project, not an official YouTube or Google product.

## Getting started

- Use Python 3.10 or later and install the dependencies listed in `requirements.txt` into a virtual environment.
- In Google Cloud, create your own project and enable both YouTube Data API v3 and YouTube Analytics API.
- Configure OAuth consent. While the app is in testing, list the Google account you intend to authorize as a test user where required. Create a Desktop application OAuth client and keep the downloaded client JSON private.
- Place the downloaded credentials in the project directory under the filename expected by `auth_setup.py`, then execute that script on a computer with a browser. Sign in to the channel owner account and grant read-only access. The generated token is sensitive: store it privately and never commit it.
- Make a local environment file using `.env.example` as a template. Generate a strong unique random bearer token and set `MCP_BEARER_TOKEN`. The Google token and MCP bearer token are different secrets.
- Start `server.py`. The default listener is loopback only. The MCP endpoint path is `/mcp`; a client must be able to send a bearer Authorization header. Run the tests in `tests/` using Python unittest.

## Remote deployment and safety

For a remote client, place a properly configured HTTPS reverse proxy in front of the loopback service and restrict access. Configure the allowed public host in `MCP_ALLOWED_HOSTS`; allow browser origins explicitly only if needed. Avoid logging tokens or request bodies. TLS setup is not supplied by this repository.

Anyone with the MCP bearer token can read the authorized account's data. This project is intended for one owner and is not a multi-user service. Do not share credentials between users. `.gitignore` reduces accidental commits but does not secure a running service. Rotate leaked secrets promptly. Google OAuth testing mode and verification requirements may affect refresh-token lifetime and broader distribution.

The tests use mocks. Live Google authorization, metrics, remote deployment and compatibility with a particular MCP client have not been verified. API usage is subject to the limits of the Google Cloud project in use.
