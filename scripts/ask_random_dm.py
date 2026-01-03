if not CHANNEL_ID:
    raise RuntimeError("SLACK_CHANNEL_ID is not set or empty (should be like C0123456789).")

import os
import random
import requests

TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]

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
    res = slack("conversations.members", {"channel": CHANNEL_ID, "limit": 200, "cursor": cursor})
    members.extend(res["members"])
    cursor = res.get("response_metadata", {}).get("next_cursor")
    if not cursor:
        break

# 2) Pick a random member
picked = random.choice(members)

# 3) Open DM with that member
dm = slack("conversations.open", {"users": picked})
dm_id = dm["channel"]["id"]

# 4) Send the question
slack("chat.postMessage", {"channel": dm_id, "text": QUESTION})
print("picked:", picked)
print("sent")
