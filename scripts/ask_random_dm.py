import os
import random
import requests

TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

if not TOKEN:
    raise RuntimeError("SLACK_BOT_TOKEN is not set.")
if not CHANNEL_ID:
    raise RuntimeError("SLACK_CHANNEL_ID is not set or empty (should look like C0123456789 or G0123456789).")

QUESTION = "【テスト質問】最近ハマってるものは？（このDMに返信してね）"

def slack(method, payload):
    r = requests.post(
        f"https://slack.com/api/{method}",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"{method} failed: {data}")
    return data

# 1) Get channel members
members = []
cursor = None
while True:
    payload = {"channel": CHANNEL_ID, "limit": 200}
    if cursor:
        payload["cursor"] = cursor
    res = slack("conversations.members", payload)
    members.extend(res.get("members", []))
    cursor = res.get("response_metadata", {}).get("next_cursor")
    if not cursor:
        break

if not members:
    raise RuntimeError(f"No members found in channel {CHANNEL_ID}. Is the channel ID correct and is the bot in the channel?")

# 2) Pick a random member
picked = random.choice(members)

# 3) Open DM with that member
dm = slack("conversations.open", {"users": picked})
dm_id = dm["channel"]["id"]

# 4) Send the question
slack("chat.po
