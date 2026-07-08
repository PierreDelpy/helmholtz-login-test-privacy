import os
import json
import html

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
ROOT_PATH = os.getenv("ROOT_PATH", "/logintest")
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "https://login-dev.helmholtz.de/oauth2")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "please-change-me")
OIDC_SCOPE = os.getenv(
    "OIDC_SCOPE",
    "openid profile email eduperson_scoped_affiliation",
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

oauth = OAuth()
oauth.register(
    name="helmholtz",
    client_id=OIDC_CLIENT_ID,
    client_secret=OIDC_CLIENT_SECRET,
    server_metadata_url=f"{OIDC_ISSUER}/.well-known/openid-configuration",
    client_kwargs={"scope": OIDC_SCOPE},
)

def first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v

def derive_institute(u: dict) -> str:
    return (
        first(u.get("eduperson_scoped_affiliation"))
        or first(u.get("voperson_external_affiliation"))
        or (u.get("email", "").split("@", 1)[1] if "@" in u.get("email", "") else None)
        or "unknown institute"
    )

def render_page(user=None):
    if not user:
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Login test</title>
</head>
<body>
  <h1>Helmholtz login test</h1>
  <p><a href="{ROOT_PATH}/login">Login with Helmholtz ID</a></p>
</body>
</html>"""

    rows = []
    for k, v in sorted(user["claims"].items()):
        filled = "yes" if v not in (None, "", [], {}) else "no"
        pretty = html.escape(json.dumps(v, indent=2, ensure_ascii=False)) if isinstance(v, (dict, list)) else html.escape(str(v))
        rows.append(f"<tr><td>{html.escape(str(k))}</td><td>{filled}</td><td><pre>{pretty}</pre></td></tr>")

    raw = html.escape(json.dumps(user["claims"], indent=2, ensure_ascii=False))

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Protected profile view</title>
  <style>
    body {{ font-family: sans-serif; max-width: 1000px; margin: 2rem auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; vertical-align: top; text-align: left; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <h1>Protected profile view</h1>

  <p><strong>Hello {html.escape(user["name"])} from {html.escape(user["institute"])}</strong></p>

  <p><strong>Name:</strong> {html.escape(user["name"])}</p>
  <p><strong>Email:</strong> {html.escape(user["email"])}</p>

  <h2>Returned claims</h2>
  <table>
    <tr><th>Claim</th><th>Filled?</th><th>Value</th></tr>
    {''.join(rows)}
  </table>

  <h2>Raw userinfo</h2>
  <pre>{raw}</pre>

  <p><a href="{ROOT_PATH}/logout">Logout</a></p>
</body>
</html>"""

@app.get(ROOT_PATH, response_class=HTMLResponse)
async def home(request: Request):
    return HTMLResponse(render_page(request.session.get("user")))

@app.get(f"{ROOT_PATH}/login")
async def login(request: Request):
    redirect_uri = f"{BASE_URL}{ROOT_PATH}/auth/callback"
    return await oauth.helmholtz.authorize_redirect(request, redirect_uri)

@app.get(f"{ROOT_PATH}/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.helmholtz.authorize_access_token(request)
    userinfo = await oauth.helmholtz.userinfo(token=token)

    given = userinfo.get("given_name", "")
    family = userinfo.get("family_name", "")
    name = userinfo.get("name") or f"{given} {family}".strip() or "Unknown user"

    request.session["user"] = {
        "name": name,
        "email": userinfo.get("email") or "not provided",
        "institute": derive_institute(userinfo),
        "claims": userinfo,
    }
    return RedirectResponse(url=ROOT_PATH, status_code=302)

@app.get(f"{ROOT_PATH}/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url=ROOT_PATH, status_code=302)
