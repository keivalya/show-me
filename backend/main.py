import os
import logging
import asyncio
import json
import base64

import requests
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from pydantic import BaseModel

from google.genai import Client
from google.genai.types import Blob, Content, Part

from agents.identifier import IdentifierAgent
from agents.director import DirectorAgent
from clients.youtube import YouTubeClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY is not set; agents will fail to call Gemini.")

client = Client(api_key=GOOGLE_API_KEY, http_options={"api_version": "v1alpha"})
identifier_agent = IdentifierAgent(client)
director_agent = DirectorAgent(client)
youtube_client = YouTubeClient(os.getenv("YOUTUBE_API_KEY", GOOGLE_API_KEY))

LIVE_MODEL = os.getenv("LIVE_MODEL", "gemini-3.1-flash-live-preview")
LIVE_ENABLED = os.getenv("LIVE_ENABLED", "true").lower() != "false"


@app.get("/health")
async def health_check():
    return {"status": "ok"}


class DiagnoseRequest(BaseModel):
    image_base64: str
    transcript: str = ""


DIAGNOSE_PROMPT = """You are Show Me, an AI repair assistant for kitchen appliances.
The user shared one photo of an appliance plus a spoken description of the problem.

Look at the image AND the spoken description together. Identify the appliance
(make/model if visible) and diagnose the most likely cause.

Output STRICT JSON only, no prose, no markdown fences:
{
  "appliance": "string (e.g. 'Nespresso Vertuo Plus')",
  "symptom": "string (one-line problem)",
  "summary": "string (one-sentence diagnosis and approach)",
  "steps": ["string", ...],
  "safety_notes": ["string", ...]
}

Rules:
- 3-6 concrete steps, each under 20 words.
- Include safety_notes only when there's a real risk (electrical, hot, sharp,
  pressurized). Empty array otherwise.
- If the photo isn't clear, still give your best guess from the description.
- Never invent torque values, part numbers, or warranty info.
"""


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest):
    try:
        img_bytes = base64.b64decode(req.image_base64)
    except Exception:
        return {"error": "bad image_base64"}

    parts = [
        Part.from_text(text=DIAGNOSE_PROMPT),
        Part.from_text(text=f"User said: {req.transcript or '(no description provided)'}"),
        Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
    ]

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[Content(role="user", parts=parts)],
            config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)
    except Exception as e:
        logger.exception(f"Diagnose failed: {e}")
        return {
            "error": str(e),
            "appliance": "Unknown",
            "symptom": "",
            "summary": "Sorry, I couldn't diagnose this. Please try again.",
            "steps": [],
            "safety_notes": [],
        }


def lookup_procedure(make, model, symptom):
    try:
        if not os.path.exists("procedure_db.json"):
            return None
        with open("procedure_db.json", "r") as f:
            db = json.load(f)

        for entry in db:
            if entry["appliance"]["make"].lower() in (make or "").lower() and \
               entry["appliance"]["model"].lower() in (model or "").lower():
                return entry
        return None
    except Exception as e:
        logger.error(f"Procedure DB lookup failed: {e}")
        return None


def get_coach_prompt(make, model, symptom, procedure):
    with open("prompts/coach.txt", "r") as f:
        template = f.read()

    steps = procedure.get("steps") or procedure.get("procedure_steps") or []
    numbered_steps = "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))

    return template.format(
        make=make,
        model=model,
        symptom=symptom,
        procedure_source="procedure_db",
        verified=procedure.get("verified", False),
        numbered_steps=numbered_steps,
        step_timestamps=json.dumps(procedure.get("step_timestamps", []))
    )


def url_is_reachable(url, timeout=2.0):
    """Quick HEAD check so we don't push a 404 video URL to the client."""
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        return r.status_code == 200
    except Exception as e:
        logger.info(f"HEAD check failed for {url}: {e}")
        return False


async def open_live_session():
    """Try to open a Gemini Live session. Returns the async ctx manager or None."""
    if not LIVE_ENABLED:
        return None
    try:
        return await client.aio.live.connect(model=LIVE_MODEL).__aenter__()
    except Exception as e:
        logger.warning(f"Could not open Live session ({LIVE_MODEL}): {e}")
        return None


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    frames_buffer = []
    user_text_buffer = []
    flow_started = False

    # Live is optional — if it fails we still run the Identifier/Director flow.
    live_session = None
    if LIVE_ENABLED:
        try:
            live_ctx = client.aio.live.connect(model=LIVE_MODEL)
            live_session = await live_ctx.__aenter__()
            logger.info(f"Connected to Gemini Live session ({LIVE_MODEL})")
        except Exception as e:
            logger.warning(f"Live session unavailable: {e}")
            live_session = None
            live_ctx = None
    else:
        live_ctx = None

    async def safe_live_send_media(raw, mime):
        if not live_session:
            return
        try:
            await live_session.send_realtime_input(media=Blob(data=raw, mime_type=mime))
        except Exception as e:
            logger.debug(f"Live media send failed for {mime}: {e}")

    async def safe_live_send_text(text):
        if not live_session:
            return
        try:
            await live_session.send_realtime_input(text=text)
        except Exception as e:
            logger.debug(f"Live text send failed: {e}")

    async def run_full_flow(frames, user_text):
        try:
            identified_data = await identifier_agent.identify(frames, user_text)
            await websocket.send_json({"type": "identification", "data": identified_data})

            procedure_match = lookup_procedure(
                identified_data.get("make", ""),
                identified_data.get("model", ""),
                identified_data.get("symptom", "")
            )

            youtube_results = youtube_client.search_repair_video(
                identified_data.get("make", ""),
                identified_data.get("model", ""),
                identified_data.get("symptom", "")
            )

            director_decision = await director_agent.route(
                identified_data,
                youtube_results=youtube_results,
                procedure_db_match=procedure_match
            )
            await websocket.send_json({"type": "director_decision", "data": director_decision})

            if director_decision.get("path") == "escalate":
                await websocket.send_json({
                    "type": "escalate",
                    "message": director_decision.get("user_message", "Cannot help with this safely.")
                })
                return

            # Pick a video. If the cached MP4 isn't reachable (typical in local
            # dev because the GCS bucket isn't populated), fall back to the first
            # YouTube result so the browser doesn't 404 the <video> element.
            if director_decision.get("path") == "youtube" and director_decision.get("video_id"):
                await websocket.send_json({
                    "type": "youtube_video",
                    "video_id": director_decision["video_id"],
                    "start_ts": director_decision.get("start_ts", 0)
                })
            else:
                cached_url = (procedure_match or {}).get("cached_video_url")
                if cached_url and url_is_reachable(cached_url):
                    await websocket.send_json({"type": "video_url", "url": cached_url})
                elif youtube_results:
                    first = youtube_results[0]
                    logger.info(f"Cached MP4 unavailable; falling back to YouTube: {first['video_id']}")
                    await websocket.send_json({
                        "type": "youtube_video",
                        "video_id": first["video_id"],
                        "start_ts": 0
                    })
                else:
                    logger.warning("No video available (no cached MP4, no YouTube results).")

            coach_prompt = get_coach_prompt(
                identified_data.get("make", ""),
                identified_data.get("model", ""),
                identified_data.get("symptom", ""),
                director_decision if director_decision.get("procedure_steps") else (procedure_match or {})
            )
            await safe_live_send_text(f"SYSTEM UPDATE: {coach_prompt}")
        except Exception as e:
            logger.exception(f"run_full_flow failed: {e}")

    async def receive_from_client():
        nonlocal flow_started
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
            except Exception:
                continue

            if data.get("type") == "realtime_input":
                for chunk in data.get("media_chunks", []):
                    mime = chunk.get("mime_type", "")
                    b64 = chunk.get("data", "")
                    if not b64:
                        continue
                    try:
                        raw = base64.b64decode(b64)
                    except Exception:
                        continue

                    if mime.startswith("image/") and len(frames_buffer) < 8:
                        frames_buffer.append(raw)

                    await safe_live_send_media(raw, mime)

                    if len(frames_buffer) >= 8 and not flow_started:
                        flow_started = True
                        user_text = " ".join(user_text_buffer)
                        asyncio.create_task(run_full_flow(list(frames_buffer), user_text))

            elif data.get("type") == "text":
                txt = data.get("text", "")
                user_text_buffer.append(txt)
                await safe_live_send_text(txt)

    async def send_to_client():
        if not live_session:
            return
        try:
            async for response in live_session.receive():
                sc = getattr(response, "server_content", None)
                if sc and getattr(sc, "model_turn", None):
                    parts = sc.model_turn.parts or []
                    for part in parts:
                        if getattr(part, "inline_data", None) and part.inline_data.data:
                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(part.inline_data.data).decode("utf-8")
                            })
                        elif getattr(part, "text", None):
                            await websocket.send_json({"type": "text", "text": part.text})

                if getattr(response, "tool_call", None):
                    for call in response.tool_call.function_calls:
                        logger.info(f"Tool call: {call.name}({call.args})")
                        await websocket.send_json({
                            "type": "tool_call",
                            "name": call.name,
                            "args": dict(call.args) if call.args else {}
                        })
        except Exception as e:
            logger.warning(f"Live receive stopped: {e}")

    try:
        await asyncio.gather(receive_from_client(), send_to_client())
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if live_ctx is not None:
            try:
                await live_ctx.__aexit__(None, None, None)
            except Exception:
                pass
        if websocket.client_state.name != "DISCONNECTED":
            try:
                await websocket.close()
            except Exception:
                pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
