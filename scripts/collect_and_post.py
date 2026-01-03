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


def slack_get(method: str, params: dict):
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


def slack_post(method: str, payload: dict):
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


def find_reply(dm_id: str, user_id: str, thread_ts: str):
    # スレッドの親(ts)にぶら下がる返信を取得
    res = slack_get("conversations.replies", {
        "channel": dm_id,
        "ts": str(thread_ts),
        "limit": 200
    })

    # messages[0] が親（質問）で、messages[1:] が返信
    for m in res.get("messages", [])[1:]:
        if m.get("user") == user_id and m.get("text"):
            return m["text"]

    return None



def main():
    state = load_state()
    pending = state.get("pending", [])

    new_pending = []
    for p in pending:
        user = p["user"]
        dm = p["dm"]
        q = p["question"]
        thread_ts = p["thread_ts"]   # ← ここ

        answer = find_reply(dm, user, thread_ts)  # ← ここ
        if answer:
            text = f"🎤 <@{user}> の回答\n*Q:* {q}\n*A:* {answer}"
            slack_post("chat.postMessage", {"channel": CHANNEL_ID, "text": text})
        else:
            new_pending.append(p)


    state["pending"] = new_pending
    save_state(state)
    print("done")


if __name__ == "__main__":
    main()
