"""
Database layer — In-memory storage with optional MongoDB fallback.
Uses in-memory dict if MongoDB is unavailable (for Render free tier / testing).
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Try MongoDB first ─────────────────────────────────────────────────────────
_mongo_available = False
_sessions_col = None
_leads_col = None

try:
    from pymongo import MongoClient
    from app.config import settings
    _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    _client.admin.command("ping")  # Quick connection test
    _db = _client[settings.MONGODB_DB_NAME]
    _sessions_col = _db["sessions"]
    _leads_col = _db["leads"]
    _sessions_col.create_index("instagram_id", unique=True)
    _leads_col.create_index("instagram_id")
    _mongo_available = True
    logger.info("✅ MongoDB connected!")
except Exception as e:
    logger.warning(f"⚠️ MongoDB unavailable — using in-memory storage: {e}")
    _mongo_available = False

# ── In-memory fallback ────────────────────────────────────────────────────────
_sessions: dict = {}
_leads: list = []


# ── Public interface (works regardless of backend) ────────────────────────────

def get_session(instagram_id: str) -> Optional[dict]:
    if _mongo_available:
        return _sessions_col.find_one({"instagram_id": instagram_id})
    return _sessions.get(instagram_id)


def create_session(instagram_id: str) -> dict:
    session = {
        "instagram_id": instagram_id,
        "conversation_history": [],
        "collected": {
            "training_status": None, "primary_goal": None,
            "weight_target": None, "struggle_duration": None,
            "main_obstacle": None, "motivation_level": None
        },
        "intent": "unknown", "stage": "qualifying", "activated": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    if _mongo_available:
        try:
            _sessions_col.insert_one(session)
        except Exception:
            _sessions_col.update_one(
                {"instagram_id": instagram_id},
                {"$set": session}, upsert=True
            )
    else:
        _sessions[instagram_id] = session
    logger.info(f"✅ Session created: {instagram_id}")
    return session


def update_session(instagram_id: str, updates: dict):
    updates["updated_at"] = datetime.now(timezone.utc)
    if _mongo_available:
        _sessions_col.update_one({"instagram_id": instagram_id}, {"$set": updates})
    else:
        if instagram_id in _sessions:
            # Handle nested updates like "collected.training_status"
            for key, value in updates.items():
                if "." in key:
                    parts = key.split(".", 1)
                    if parts[0] not in _sessions[instagram_id]:
                        _sessions[instagram_id][parts[0]] = {}
                    _sessions[instagram_id][parts[0]][parts[1]] = value
                else:
                    _sessions[instagram_id][key] = value


def add_message_to_history(instagram_id: str, role: str, content: str):
    msg = {"role": role, "content": content, "timestamp": datetime.now(timezone.utc)}
    if _mongo_available:
        _sessions_col.update_one(
            {"instagram_id": instagram_id},
            {"$push": {"conversation_history": msg},
             "$set": {"updated_at": datetime.now(timezone.utc)}}
        )
    else:
        if instagram_id in _sessions:
            _sessions[instagram_id].setdefault("conversation_history", []).append(msg)


def save_lead(instagram_id: str, session: dict):
    lead = {
        "instagram_id": instagram_id,
        "collected": session.get("collected", {}),
        "intent": session.get("intent", "unknown"),
        "stage": "booked",
        "created_at": datetime.now(timezone.utc)
    }
    if _mongo_available:
        _leads_col.insert_one(lead)
    else:
        _leads.append(lead)
    logger.info(f"🎯 Lead saved: {instagram_id}")


def is_session_active(instagram_id: str) -> bool:
    if _mongo_available:
        return _sessions_col.find_one(
            {"instagram_id": instagram_id, "activated": True}, {"_id": 1}
        ) is not None
    session = _sessions.get(instagram_id)
    return session is not None and session.get("activated", False)


# ── Admin helpers (used by /leads and /session endpoints) ─────────────────────
def get_all_leads(limit: int = 50) -> list:
    if _mongo_available:
        leads = list(_leads_col.find({}, {"_id": 0}).sort("created_at", -1).limit(limit))
        for l in leads:
            if "created_at" in l:
                l["created_at"] = l["created_at"].isoformat()
        return leads
    return [
        {**l, "created_at": l["created_at"].isoformat()}
        for l in reversed(_leads[-limit:])
    ]


def delete_session(instagram_id: str):
    if _mongo_available:
        _sessions_col.delete_one({"instagram_id": instagram_id})
    else:
        _sessions.pop(instagram_id, None)
