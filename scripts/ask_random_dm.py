import os
import random
import requests

TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")
BOT_USER_ID = os.environ.get("SLACK_BOT_USER_ID")


if not TOKEN:
    raise RuntimeError("SLACK_BOT_TOKEN is not set.")
if not CHANNEL_ID:
    raise RuntimeError("SLACK_CHANNEL_ID is not set or empty.")

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

# 1) Get channel members (GET with query params)
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

if not members:
    raise RuntimeError("No members found. Is the bot invited to the channel?")

# 2) Pick random member
human_members = [u for u in members if u != BOT_USER_ID]

if not human_members:
    raise RuntimeError("No human members found (only bots?).")

picked = random.choice(human_members)

# 3) Open DM
dm = slack_post("conversations.open", {"users": picked})
dm_id = dm["channel"]["id"]

# 4) Send question
slack_post("chat.postMessage", {"channel": dm_id, "text": QUESTION})

print("picked:", picked)
print("sent")
