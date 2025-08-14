
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import os, time, logging

from n2p import N2PClient, N2PConfig
from utils_us import is_valid_us_e164, within_quiet_hours_et

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kommo-n2p-backend")

APP_VERSION = "1.0.0"

app = FastAPI(title="Kommo x net2phone Backend (US)", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SendSmsPayload(BaseModel):
    to: str = Field(..., description="E.164 US: +1XXXXXXXXXX")
    text: str
    sender: Optional[str] = None
    subdomain: Optional[str] = None
    lead_id: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None

router = APIRouter()

@router.get("/webhooks/dp")
async def dp_probe():
    return {"ok": True}

@router.post("/webhooks/dp")
async def dp_handler(req: Request):
    payload = await req.json()
    logger.info(f"[DP] {payload}")
    return {"received": True}

@router.get("/webhooks/uninstalled")
async def uninstalled_probe():
    return {"ok": True}

@router.post("/webhooks/uninstalled")
async def uninstalled(req: Request):
    data = await req.json()
    logger.info(f"[UNINSTALLED] {data}")
    return {"ok": True}

@router.post("/webhooks/n2p")
async def webhooks_n2p(request: Request):
    body = await request.json()
    logger.info(f"[WEBHOOK N2P] {body}")
    return {"ok": True}

app.include_router(router)

@app.get("/")
def root():
    return {"status":"ok","service":"kommo-n2p-backend","version":APP_VERSION,"time":int(time.time())}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

BRAND_TAG = os.getenv("BRAND_TAG", "PLS N2P")
ALLOWED_START = int(os.getenv("ALLOWED_HOURS_START", "8"))
ALLOWED_END   = int(os.getenv("ALLOWED_HOURS_END", "21"))
DEFAULT_SENDER = os.getenv("DEFAULT_SENDER", "+17543050540")

def decorate_text(text: str) -> str:
    base = f"[{BRAND_TAG}] {text}"
    return f"{base} Reply STOP to opt-out."

@app.get("/send-sms")
def send_sms_probe():
    return {"ok": True}

@app.post("/send-sms")
def send_sms(payload: SendSmsPayload):
    if not is_valid_us_e164(payload.to):
        raise HTTPException(status_code=400, detail="Invalid US E.164 number (+1XXXXXXXXXX)")
    if within_quiet_hours_et(start_hour=ALLOWED_START, end_hour=ALLOWED_END):
        raise HTTPException(status_code=429, detail="Quiet hours in effect (8am–9pm ET by default)")

    mock = os.getenv("MOCK_SEND", "true").lower() == "true"
    msg = decorate_text(payload.text)
    sender = payload.sender or DEFAULT_SENDER

    if mock:
        logger.info(f"[MOCK] to={payload.to} len={len(msg)} sender={sender}")
        return {"status": "queued", "provider":"net2phone", "mock": True, "echo": {"to":payload.to, "text": msg, "sender": sender}}

    cfg = N2PConfig.from_env()
    client = N2PClient(cfg)
    try:
        result = client.send_sms(to=payload.to, text=msg, sender=sender)
        logger.info(f"[N2P] {result}")
        return {"status":"queued","provider":"net2phone","mock":False,"result":result}
    except Exception as e:
        logger.exception("N2P send failed")
        raise HTTPException(status_code=502, detail=str(e))
