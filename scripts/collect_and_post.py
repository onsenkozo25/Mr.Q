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


def find_reply(dm_id: str, user_id: str, asked_at_ts: str):
    res = slack_get("conversations.history", {
        "channel": dm_id,
        "limit": 20,
        "inclusive": True
    })

    print("---- history debug (no text) ----")
    print("asked_at_ts:", asked_at_ts)

    for m in res.get("messages", []):
        ts = m.get("ts")
        has_text = bool(m.get("text"))
        is_bot = bool(m.get("bot_id")) or (m.get("subtype") == "bot_message")
        u = m.get("user")
        subtype = m.get("subtype")
        print("ts:", ts, "user:", u, "bot:", is_bot, "subtype:", subtype, "has_text:", has_text)

    # ここから回答探索（いまは “質問より後” を優先）
    for m in res.get("messages", []):
        if m.get("bot_id") or m.get("subtype") == "bot_message":
            continue
        if not m.get("text"):
            continue
        try:
            if float(m.get("ts", 0)) <= float(asked_at_ts):
                continue
        except ValueError:
            continue
        return m["text"]

    # フォールバック：質問より後が無いなら「最新の非botメッセージ」を拾う（テスト用）
    for m in res.get("messages", []):
        if m.get("bot_id") or m.get("subtype") == "bot_message":
            continue
        if m.get("text"):
            print("fallback picked ts:", m.get("ts"))
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
        asked_at = p["asked_at"]  # Slack ts string

        print("checking user:", user, "dm:", dm, "asked_at:", asked_at)

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


if __name__ == "__main__":
    main()
