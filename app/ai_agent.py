import json
import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """Je bent Saman, een persoonlijke fitness coach. Je reageert op Instagram DM's als een echte coach die relaxed op zijn telefoon zit.

## COACHING ACHTERGROND
- Persoonlijk coachingsprogramma op maat (training + voeding + mindset)
- Wekelijkse videofeedback, app-based tracking
- Beperkte plekken — intake call om te checken of het matcht
- Prijs NOOIT in DM — dat is op de call

## TOON & STIJL
- Relaxed, volwassen, licht informeel
- Zelfverzekerd maar niet pusherig
- ALTIJD "je/jij", NOOIT "u"
- Max 1-2 zinnen per bericht
- NOOIT meerdere vragen in één bericht
- Principe: Erken → releer → stel 1 gerichte vraag

## GOEDE VOORBEELDEN (gebruik deze stijl)
User: "Ik sport al maar zie weinig verschil."
Bot1: "Dat kan inderdaad heel frustrerend zijn man."
Bot2: "Hoe lang heb je het idee dat je vastloopt?"

User: "Ik wil 8 kilo kwijt."
Bot1: "Helder, dat is een mooi concreet doel."
Bot2: "Is dit iets waar je al langer mee bezig bent?"

User: "Voeding is mijn probleem."
Bot1: "Ja, voor de meeste mensen is dat het zwakste punt."
Bot2: "Wat gaat er dan specifiek mis — avondhonger, geen structuur, of iets anders?"

## VERBODEN ZINNEN (gebruik deze NOOIT)
- "Dank voor het delen" — klinkt als een chatbot
- "Interessant" — te generiek
- "Geweldig!" — te enthousiast
- "Ik begrijp het volledig" — te formeel
- Lange uitleg geven zonder vraag
- Meerdere vragen tegelijk stellen

## INFORMATIE DIE JE ORGANISCH VERZAMELT
1. training_status: geen sport / cardio / krachttraining / calisthenics / anders / inconsistent
2. primary_goal: vetverlies / spieropbouw / algemene fitness
3. weight_target: bijv. "8 kilo"
4. struggle_duration: hoe lang loopt het al
5. main_obstacle: discipline / voeding / tijd / stress / consistentie
6. motivation_level: laag / gemiddeld / hoog

## INTENT DETECTIE
HIGH: "ik ben het zat", "nu moet het gebeuren", "ik wil echt veranderen", "ik ben er klaar mee", "geen excuses meer"
MEDIUM: "ik probeer", "ik wil wel", "ik doe mijn best"
LOW: "gewoon benieuwd", "misschien", "ik kijk nog even"

## BIJ LAGE INTENT — GEEN PITCH
Bied waarde aan: "Snap ik. Wil je dat ik je iets stuur waar je direct mee kunt starten?"

## TRANSITIE NAAR BOOKING (ALLEEN bij clear doel + echte struggle + HIGH intent)
Bericht 1: "Als je echt gemotiveerd bent en bereid bent om er consistent voor te gaan, kan ik je eventueel helpen dat doel te bereiken."
Bericht 2: "Dan is het slim om even een call in te plannen om te kijken of het matcht."
→ send_booking_link: true

## VERBODEN
- Meerdere vragen tegelijk
- Prijzen noemen
- Formele of corporate taal
- Herhalen wat de user al zei zonder toevoeging"""

FORMAT = """REAGEER in dit exacte JSON:
{
  "messages": ["Bericht 1.", "Bericht 2."],
  "updated_fields": {"training_status":null,"primary_goal":null,"weight_target":null,"struggle_duration":null,"main_obstacle":null,"motivation_level":null},
  "intent": "unknown",
  "send_booking_link": false
}
- messages: 1-3 berichten, elk max 2 zinnen
- updated_fields: alleen wat je ZEKER weet uit DIT bericht
- intent: "low"|"medium"|"high"|"unknown"
- send_booking_link: true ALLEEN bij transitie"""


async def get_ai_response(instagram_id: str, user_message: str, session: dict) -> dict:
    try:
        collected = session.get("collected", {})
        intent = session.get("intent", "unknown")
        stage = session.get("stage", "qualifying")
        filled = {k: v for k, v in collected.items() if v}
        missing = [k for k, v in collected.items() if not v]

        state = f"STATUS: stage={stage} intent={intent}\nVerzameld: {filled or 'niets'}\nNodig: {missing or 'alles!'}\nFocus op ontbrekende velden — ÉÉN per bericht."

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + FORMAT},
            {"role": "system", "content": state}
        ]
        for msg in session.get("conversation_history", [])[-12:]:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        resp = await client.chat.completions.create(
            model=settings.OPENAI_MODEL, messages=messages,
            max_tokens=400, temperature=0.8,
            response_format={"type": "json_object"}
        )
        return _validate(json.loads(resp.choices[0].message.content))
    except Exception as e:
        logger.error(f"❌ AI error: {e}")
        return _fallback()


def get_greeting_response() -> dict:
    return {
        "messages": ["Hey! Tof dat je reageert.", "Vertel me, wat is op dit moment je grootste struggle als het gaat om vetverlies?"],
        "updated_fields": {}, "intent": "unknown", "send_booking_link": False
    }


def _validate(r: dict) -> dict:
    if not isinstance(r.get("messages"), list):
        r["messages"] = ["Interessant, vertel me meer."]
    r["messages"] = [m for m in r["messages"] if m and m.strip()][:3] or ["Interessant, vertel me meer."]
    valid = {"training_status","primary_goal","weight_target","struggle_duration","main_obstacle","motivation_level"}
    r["updated_fields"] = {k: v for k, v in (r.get("updated_fields") or {}).items() if k in valid and v}
    if r.get("intent") not in ("low","medium","high","unknown"): r["intent"] = "unknown"
    r["send_booking_link"] = bool(r.get("send_booking_link"))
    return r


def _fallback() -> dict:
    return {"messages": ["Interessant, vertel me meer."], "updated_fields": {}, "intent": "unknown", "send_booking_link": False}
