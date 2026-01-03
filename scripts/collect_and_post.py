import os
import json
import requests

TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")
STATE_PATH = "state/state.json"

if not TOKEN:
    raise RuntimeError("SLACK_BOT_TOKEN is not set.")
if not CHANNEL_ID:
    raise RuntimeError("SLACK_CHANNEL_ID is not set or empty.")

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

def find_reply(dm_id, user_id, asked_at):
    # asked_at以降のDM履歴を取得
    res = slack_get("conversations.history", {"channel": dm_id, "oldest": str(asked_at)})
    for m in res.get("messages", []):
        if m.get("type") == "message" and m.get("user") == user_id and m.get("text"):
            return m["text"]
    return None

def main():
    state = load_state()
    pending = state.get("pending", [])
    print("pending count:", len(pending))

    if not pending:
        print("No pending.")
        return

    new_pending = []
    for p in pending:
        user = p["user"]
        dm = p["dm"]
        q = p["question"]
        asked_at = p["asked_at"]

        print("checking user:", user, "dm:", dm)

        answer = find_reply(dm, user, asked_at)
        print("answer found:", bool(answer))

        if answer:
            text = f"🎤 <@{user}> の回答\n*Q:* {q}\n*A:* {answer}"
            slack_post("chat.postMessage", {"channel": CHANNEL_ID, "text": text})
            print("posted to channel")
        else:
            new_pending.append(p)

    state["pending"] = new_pending
    save_state(state)
    print("done")


    state["pending"] = new_pending
    save_state(state)
    print("done")

if __name__ == "__main__":
    main()
