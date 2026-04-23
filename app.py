from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
from starlette.responses import Response
from dotenv import load_dotenv
import requests
import signal
import sys
import os

load_dotenv(".env")

SECRET = os.getenv("SECRET")
if not SECRET:
    os.kill(os.getppid(), signal.SIGTERM)
    sys.exit("NO SECRET SET!")
TOKEN = os.getenv("TOKEN")
BASE = "https://discord.com/api/v9/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Authorization": TOKEN,
    "X-Discord-Locale": "en-US",
    "X-Debug-Options": "bugReporterEnabled",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

session = requests.Session()
session.headers = HEADERS

templates = Jinja2Templates(directory="templates")

async def home(request):
    return templates.TemplateResponse(request, "home.html")

async def dms(request):
    if request.cookies.get("secret") != SECRET:
        return templates.TemplateResponse(request, "error.html", context={"code": 401}, status_code=401)

    req = session.get(BASE + "users/@me/channels")

    sorted_dms = sorted(req.json(), key=lambda u: (u["last_message_id"] is not None, int(u["last_message_id"]) if u["last_message_id"] is not None else u["last_message_id"]), reverse=True)

    ctx = []
    for u in sorted_dms:
        channel = {
            "id": u["id"],
            "recipients": 0
        }

        rcps = []
        for r in u["recipients"]:
            rcps.append({
                "id": r["id"],
                "name": r["global_name"],
                "pfp": r["avatar"]
            })
        channel["recipients"] = rcps

        ctx.append(channel)

    return templates.TemplateResponse(request, "dms.html", context={"ctx": ctx})

async def dm(request):
    if request.cookies.get("secret") != SECRET:
        return templates.TemplateResponse(request, "error.html", context={"code": 401}, status_code=401)

    limit = 10
    if "limit" in request.query_params:
        limit = request.query_params["limit"]

    channel_id = request.path_params["channel"]

    req = session.get(BASE + f"channels/{channel_id}/messages?limit={limit}")

    ctx = [channel_id]
    for m in req.json():
        if m["type"] in [0, 19]:
            msg = {
                "id": m["id"],
                "author": {
                    "id": m["author"]["id"],
                    "name": m["author"]["global_name"],
                    "pfp": m["author"]["avatar"]
                },
                "content": m["content"],
                "timestamp": m["timestamp"],
                "reply": 0,
                "attachments": 0
            }

            if m["type"] == 19:
                try:
                    msg["reply"] = {
                        "id": m["referenced_message"]["id"],
                        "author": {
                            "id": m["referenced_message"]["author"]["id"],
                            "name": m["referenced_message"]["author"]["global_name"],
                            "pfp": m["referenced_message"]["author"]["avatar"]
                        },
                        "content": m["referenced_message"]["content"]
                    }
                except KeyError:
                    msg["reply"] = 1
                
            if len(m["attachments"]) > 0:
                msg["attachments"] = []
                for a in m["attachments"]:
                    if str(a["content_type"]).startswith("image"):
                        msg["attachments"].append({
                            "id": a["id"],
                            "url": a["proxy_url"]
                        })
                
                if len(msg["attachments"]) == 0:
                    msg["attachments"] = 0

            ctx.append(msg)

    return templates.TemplateResponse(request, "dm.html", context={"ctx": ctx})

async def send(request):
    if request.cookies.get("secret") != SECRET:
        return templates.TemplateResponse(request, "error.html", context={"code": 401}, status_code=401)

    body = await request.json()
    payload = {
        "content": body["content"]
    }

    if "reply_message_id" in body:
        payload["message_reference"] = {
            "channel_id": body["channel_id"],
            "message_id": body["reply_message_id"]
        }

    req = session.post(BASE + f"channels/{body['channel_id']}/messages", json=payload)

    if req.status_code == 200:
        return Response(status_code=200)
    else:
        return Response(status_code=500)

routes = [
    Route("/", endpoint=home),
    Route("/dms", endpoint=dms),
    Route("/dms/{channel}", endpoint=dm),
    Route("/send", endpoint=send, methods=["POST"]),
    Mount("/static", StaticFiles(directory="static"), name="static")
]

app = Starlette(routes=routes)