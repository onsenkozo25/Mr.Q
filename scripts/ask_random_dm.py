import os
import json
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


def get_channel_members(channel_id: str):
    members = []
    cursor = None
    while True:
        params = {"channel": channel_id, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        res = slack_get("conversations.members", params)
        members.extend(res.get("members", []))
        cursor = res.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return members


def main():
    # 1) members
    members = get_channel_members(CHANNEL_ID)

    # 2) exclude bot & de-dup
    members = list(dict.fromkeys(members))
    human_members = [u for u in members if u != BOT_USER_ID]
    if not human_members:
        raise RuntimeError("No human members found (only bots?).")

    # 3) pick random
    picked = random.choice(human_members)

    # 4) open DM
    dm = slack_post("conversations.open", {"users": picked})
    dm_id = dm["channel"]["id"]

    # 5) send question + capture Slack ts
    msg = slack_post("chat.postMessage", {"channel": dm_id, "text": QUESTION})
    asked_ts = msg["ts"]  # Slack message ts (string like "1700000000.123456")

    # 6) save pending
    state = load_state()
    state.setdefault("pending", [])

    state["pending"].append(
        {
            "user": picked,
            "dm": dm_id,
            "question": QUESTION.replace("【テスト質問】", "").strip(),
            "asked_at": asked_ts,  # store Slack ts (string)
        }
    )
    state["last_picked_user"] = picked
    save_state(state)

    print("picked:", picked)
    print("dm:", dm_id)
    print("asked_ts:", asked_ts)
    print("saved pending")


if __name__ == "__main__":
    main()
