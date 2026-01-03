
import os
import json
import time
import random
import requests

TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")
BOT_USER_ID = os.environ.get("SLACK_BOT_USER_ID")

if not TOKEN:
    raise RuntimeError("SLACK_BOT_TOKEN is not set.")
if not CHANNEL_ID:
    raise RuntimeError("SLACK_CHANNEL_ID is not set or empty.")
if not BOT_USER_ID:
    raise RuntimeError("SLACK_BOT_USER_ID is not set or empty.")

STATE_PATH = "state/state.json"
QUESTION = "【テスト質問】最近ハマってるものは？（このDMに返信してね）"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

def slack_get(method, params):
    r = requests.get(
        f"https://slack.com/api/{method}",
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"{method} failed: {data}")
    return data

def slack_post(method, payload):
    r = requests.post(
        f"https://slack.com/api/{method}",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"{method} failed: {data}")
    return data

def load_state():
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# 1) Get channel members
members = []
cursor = None
while True:
    params = {"channel": CHANNEL_ID, "limit": 200}
    if cursor:
        params["cursor"] = cursor
    res = slack_get("conversations.members", params)
    members.extend(res.get("members", []))
    cursor = res.get("response_metadata", {}).get("next_cursor")
    if not cursor:
        break

# 2) Exclude bot
human_members = [u for u in members if u != BOT_USER_ID]
if not human_members:
    raise RuntimeError("No human members found (only bots?).")

picked = random.choice(human_members)

# 3) Open DM
dm = slack_post("conversations.open", {"users": picked})
dm_id = dm["channel"]["id"]

# 4) Send question
slack_post("chat.postMessage", {"channel": dm_id, "text": QUESTION})

# 5) Save pending to state
state = load_state()
state.setdefault("pending", [])
asked_at = int(time.time())

state["pending"].append({
    "user": picked,
    "dm": dm_id,
    "question": QUESTION.replace("【テスト質問】", "").strip(),
    "asked_at": asked_at
})
state["last_picked_user"] = picked
save_state(state)

print("picked:", picked)
print("saved pending")
