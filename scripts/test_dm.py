import os
import requests

TOKEN = os.environ["SLACK_BOT_TOKEN"]
USER_ID = os.environ["SLACK_TEST_USER_ID"]

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

# 1) open DM channel
dm = slack("conversations.open", {"users": USER_ID})
dm_id = dm["channel"]["id"]

# 2) send DM
slack("chat.postMessage", {"channel": dm_id, "text": "✅ テストDMです（GitHub Actions から送信）"})
print("sent")
