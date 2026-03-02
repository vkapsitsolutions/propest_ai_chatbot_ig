import logging
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime
from app.config import settings
from app.instagram import send_split_messages, verify_webhook_signature
from app.ai_agent import get_ai_response, get_greeting_response
from app import database as db

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL),
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI(title="Instagram DM AI – Saman (Propest AI)", version="1.0.0")
TRIGGER_WORD = "VETVERLIES"


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Saman Instagram Bot started!")
    logger.info(f"🔑 Trigger: {TRIGGER_WORD}")


@app.get("/")
async def root():
    return {"bot": "Instagram DM AI – Saman", "status": "running", "trigger": TRIGGER_WORD}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    logger.info(f"📞 Verify — mode:{mode} token:{token}")
    if mode == "subscribe" and token == settings.INSTAGRAM_VERIFY_TOKEN:
        logger.info("✅ Webhook verified!")
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body_bytes = await request.body()
        sig = request.headers.get("X-Hub-Signature-256", "")
        if sig and not verify_webhook_signature(body_bytes, sig):
            return JSONResponse({"status": "ignored"}, status_code=200)
        body = await request.json()
        logger.info(f"📩 Webhook: {body}")
        background_tasks.add_task(process_webhook_payload, body)
        return JSONResponse({"status": "received"}, status_code=200)
    except Exception as e:
        logger.error(f"❌ Receive error: {e}")
        return JSONResponse({"status": "error"}, status_code=200)


async def process_webhook_payload(body: dict):
    try:
        if body.get("object") != "instagram":
            return
        for entry in body.get("entry", []):
            page_id = entry.get("id", "")
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if sender_id == page_id or "delivery" in event or "read" in event:
                    continue
                text = event.get("message", {}).get("text", "").strip()
                if sender_id and text:
                    await handle_dm(sender_id, text)
    except Exception as e:
        logger.error(f"❌ Payload error: {e}")


async def handle_dm(sender_id: str, text: str):
    try:
        logger.info(f"💬 DM from {sender_id}: '{text[:80]}'")

        if text.upper() == TRIGGER_WORD:
            logger.info(f"🔥 Trigger from {sender_id}")
            existing = db.get_session(sender_id)
            if not existing:
                db.create_session(sender_id)
            else:
                db.update_session(sender_id, {"activated": True, "stage": "qualifying", "intent": "unknown"})
            greeting = get_greeting_response()
            db.add_message_to_history(sender_id, "user", text)
            db.add_message_to_history(sender_id, "assistant", " ".join(greeting["messages"]))
            await send_split_messages(sender_id, greeting["messages"])
            return

        if not db.is_session_active(sender_id):
            logger.info(f"⏭️ No session for {sender_id}")
            return

        session = db.get_session(sender_id)
        if not session:
            return

        ai = await get_ai_response(sender_id, text, session)
        msgs = ai.get("messages", [])
        fields = ai.get("updated_fields", {})
        new_intent = ai.get("intent", "unknown")
        send_booking = ai.get("send_booking_link", False)

        if fields:
            db.update_session(sender_id, {f"collected.{k}": v for k, v in fields.items() if v})

        rank = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
        if rank.get(new_intent, 0) >= rank.get(session.get("intent", "unknown"), 0):
            db.update_session(sender_id, {"intent": new_intent})

        db.add_message_to_history(sender_id, "user", text)
        db.add_message_to_history(sender_id, "assistant", " ".join(msgs))

        if send_booking:
            msgs.append(f"Hier is de link: {settings.BOOKING_LINK}")
            db.update_session(sender_id, {"stage": "booked"})
            fresh = db.get_session(sender_id)
            if fresh:
                db.save_lead(sender_id, fresh)

        await send_split_messages(sender_id, msgs)
        logger.info(f"✅ Replied to {sender_id} ({len(msgs)} msgs)")

    except Exception as e:
        logger.error(f"❌ handle_dm error: {e}")


@app.get("/leads")
async def get_leads():
    leads = list(db.leads_col.find({}, {"_id": 0}).sort("created_at", -1).limit(50))
    for l in leads:
        if "created_at" in l: l["created_at"] = l["created_at"].isoformat()
    return {"total": len(leads), "leads": leads}


@app.get("/session/{instagram_id}")
async def get_session(instagram_id: str):
    s = db.get_session(instagram_id)
    if not s: raise HTTPException(404, "Not found")
    s.pop("_id", None)
    for k in ("created_at", "updated_at"):
        if k in s: s[k] = s[k].isoformat()
    for m in s.get("conversation_history", []):
        if "timestamp" in m: m["timestamp"] = m["timestamp"].isoformat()
    return s


@app.delete("/session/{instagram_id}")
async def reset_session(instagram_id: str):
    db.sessions_col.delete_one({"instagram_id": instagram_id})
    return {"status": "deleted"}
