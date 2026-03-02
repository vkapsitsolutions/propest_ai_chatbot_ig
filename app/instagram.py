import httpx
import asyncio
import logging
import random
import hmac
import hashlib
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)
GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


async def send_action(recipient_id: str, action: str = "typing_on"):
    url = f"{GRAPH_API_BASE}/me/messages"
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    headers = {"Authorization": f"Bearer {settings.INSTAGRAM_ACCESS_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            (await c.post(url, json=payload, headers=headers)).raise_for_status()
    except Exception as e:
        logger.warning(f"⚠️ sender_action failed: {e}")


async def send_message(recipient_id: str, text: str) -> dict:
    url = f"{GRAPH_API_BASE}/me/messages"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    headers = {"Authorization": f"Bearer {settings.INSTAGRAM_ACCESS_TOKEN}"}
    async with httpx.AsyncClient(timeout=15.0) as c:
        resp = await c.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        logger.info(f"✅ Sent: {text[:60]}")
        return resp.json()


async def send_split_messages(recipient_id: str, messages: List[str]):
    """Send messages with realistic 5-9 second typing delays"""
    for i, msg in enumerate(messages):
        if not msg.strip():
            continue
        await send_action(recipient_id, "typing_on")
        delay = random.uniform(5, 9)
        logger.info(f"⏳ {delay:.1f}s before msg {i+1}/{len(messages)}")
        await asyncio.sleep(delay)
        await send_action(recipient_id, "typing_off")
        await send_message(recipient_id, msg)
        if i < len(messages) - 1:
            await asyncio.sleep(1.2)


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(settings.INSTAGRAM_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.split("sha256=", 1)[1])
