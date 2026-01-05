import os
import json
import random
import requests

TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")
BOT_USER_ID = os.environ.get("SLACK_BOT_USER_ID")
ASK_COUNT = int(os.environ.get("ASK_COUNT", "3"))  # 1回に何人へ送るか（デフォルト3）

# カンマ区切りの除外ユーザーID
EXCLUDE_USER_IDS = set(
    u.strip() for u in os.environ.get("EXCLUDE_USER_IDS", "").split(",") if u.strip()
)

if not TOKEN:
    raise RuntimeError("SLACK_BOT_TOKEN is not set.")
if not CHANNEL_ID:
    raise RuntimeError("SLACK_CHANNEL_ID is not set or empty.")
if not BOT_USER_ID:
    raise RuntimeError("SLACK_BOT_USER_ID is not set or empty.")
if ASK_COUNT < 1:
    raise RuntimeError("ASK_COUNT must be >= 1.")

STATE_PATH = "state/state.json"
QUESTIONS_PATH = "questions.json"
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


def load_questions():
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    qs = data.get("questions", [])
    qs = [q.strip() for q in qs if isinstance(q, str) and q.strip()]
    if not qs:
        raise RuntimeError("questions.json has no valid questions.")
    return qs


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
    # de-dup while preserving order
    return list(dict.fromkeys(members))


def main():
    questions = load_questions()

    # 1) members
    members = get_channel_members(CHANNEL_ID)

    # 2) exclude bot + excluded IDs
    excluded = set(EXCLUDE_USER_IDS)
    excluded.add(BOT_USER_ID)

    human_members = [u for u in members if u not in excluded]

    if not human_members:
        raise RuntimeError(
            "No eligible members found. "
            "Check SLACK_CHANNEL_ID, bot membership in channel, and EXCLUDE_USER_IDS."
        )

    # 3) decide how many we can actually ask
    n = min(ASK_COUNT, len(human_members), len(questions))

    picked_users = random.sample(human_members, n)
    picked_questions = random.sample(questions, n)

    # 4) load state
    state = load_state()
    state.setdefault("pending", [])

    # 5) send DM per user with a unique question; save thread_ts per DM message
    for user_id, q in zip(picked_users, picked_questions):
        # open DM
        dm = slack_post("conversations.open", {"users": user_id})
        dm_id = dm["channel"]["id"]

        text = f"【今日の質問】{q}\n（このメッセージのスレッドに返信してね）"
        msg = slack_post("chat.postMessage", {"channel": dm_id, "text": text})
        thread_ts = msg["ts"]

        state["pending"].append(
            {
                "user": user_id,
                "dm": dm_id,
                "question": q,
                "thread_ts": thread_ts,
            }
        )

        print("sent:", user_id, "dm:", dm_id, "thread_ts:", thread_ts)

    # 6) save state
    state["last_picked_users"] = picked_users
    save_state(state)

    print("excluded:", ",".join(sorted(excluded)) if excluded else "(none)")
    print("asked_count:", n)
    print("saved pending total:", len(state["pending"]))


if __name__ == "__main__":
    main()
