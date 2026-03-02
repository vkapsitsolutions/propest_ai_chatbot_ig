import requests, time, json

BASE = "http://localhost:8000"
UID  = "demo_session_001"

def send(text):
    requests.post(f"{BASE}/webhook", json={
        "object": "instagram",
        "entry": [{"id": "34115813534734069", "messaging": [
            {"sender": {"id": UID}, "message": {"text": text}}
        ]}]
    }, timeout=10)

def get_bot_reply(wait=15):
    time.sleep(wait)
    r = requests.get(f"{BASE}/session/{UID}", timeout=5).json()
    msgs = [m["content"] for m in r.get("conversation_history", []) if m["role"] == "assistant"]
    return msgs[-1] if msgs else ""

# Clear previous session
try: requests.delete(f"{BASE}/session/{UID}")
except: pass
time.sleep(1)

print()
print("=" * 55)
print("  SAMAN BOT - LIVE CONVERSATION DEMO")
print("=" * 55)
print()

FLOW = [
    ("VETVERLIES",
     10),
    ("Ja ik train soms maar eigenlijk merk ik dat ik het heel moeilijk vol hou. Dan eet ik ook gelijk slecht als ik een dag mis. En dan zie ik gewoon niks",
     20),
    ("Al minstens 2 jaar zo. Ik weet ook niet precies wat ik fout doe, 's avonds eet ik teveel denk ik en dan geef ik het gewoon op",
     20),
    ("Ik ben het echt zat. Ik wil gewoon een keer resultaat zien. Voor mijn gevoel heb ik het al jaren geprobeerd. Nu of nooit",
     20),
]

bot_count = 0
for msg, wait in FLOW:
    print(f"  USER  : {msg}")
    send(msg)
    reply = get_bot_reply(wait)
    if reply:
        # Show each sentence on its own line, clean punctuation
        parts = [p.strip().rstrip('.') for p in reply.replace('?', '?.SPLIT').replace('!', '!.SPLIT').split('.SPLIT') if p.strip()]
        for part in parts:
            if part:
                print(f"  BOT   : {part}")
    print()

# Final collected data
print("=" * 55)
print("  DATA COLLECTED BY BOT")
print("=" * 55)
try:
    d = requests.get(f"{BASE}/session/{UID}", timeout=5).json()
    c = d.get("collected", {})
    fields = [
        ("Training Status",   c.get("training_status")),
        ("Primary Goal",      c.get("primary_goal")),
        ("Weight Target",     c.get("weight_target")),
        ("Struggle Duration", c.get("struggle_duration")),
        ("Main Obstacle",     c.get("main_obstacle")),
        ("Motivation Level",  c.get("motivation_level")),
    ]
    for label, val in fields:
        status = "OK" if val else "--"
        print(f"  [{status}]  {label:<20} : {val or 'not collected'}")
    print()
    print(f"  Intent  : {d.get('intent','').upper()}")
    print(f"  Stage   : {d.get('stage','').upper()}")
except:
    pass
print("=" * 55)
print()
