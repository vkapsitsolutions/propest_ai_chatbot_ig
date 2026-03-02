import logging
from datetime import datetime, timezone
from typing import Optional
from pymongo import MongoClient
from app.config import settings

logger = logging.getLogger(__name__)
client = MongoClient(settings.MONGODB_URI)
db = client[settings.MONGODB_DB_NAME]
sessions_col = db["sessions"]
leads_col = db["leads"]
sessions_col.create_index("instagram_id", unique=True)
leads_col.create_index("instagram_id")


def get_session(instagram_id: str) -> Optional[dict]:
    return sessions_col.find_one({"instagram_id": instagram_id})


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
    sessions_col.insert_one(session)
    return session


def update_session(instagram_id: str, updates: dict):
    updates["updated_at"] = datetime.now(timezone.utc)
    sessions_col.update_one({"instagram_id": instagram_id}, {"$set": updates})


def add_message_to_history(instagram_id: str, role: str, content: str):
    sessions_col.update_one(
        {"instagram_id": instagram_id},
        {"$push": {"conversation_history": {"role": role, "content": content,
         "timestamp": datetime.now(timezone.utc)}},
         "$set": {"updated_at": datetime.now(timezone.utc)}}
    )


def save_lead(instagram_id: str, session: dict):
    leads_col.insert_one({
        "instagram_id": instagram_id,
        "collected": session.get("collected", {}),
        "intent": session.get("intent", "unknown"),
        "stage": "booked",
        "created_at": datetime.now(timezone.utc)
    })
    logger.info(f"🎯 Lead saved: {instagram_id}")


def is_session_active(instagram_id: str) -> bool:
    return sessions_col.find_one({"instagram_id": instagram_id, "activated": True}, {"_id": 1}) is not None
