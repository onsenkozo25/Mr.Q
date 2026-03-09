import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

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


def today_key_jst():
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")


def ensure_daily_parent_post(state: dict) -> str:
    """
    その日の親投稿（今日のQuestion）の thread_ts を返す。
    なければチャンネルに作成して state に保存する。
    """
    day = today_key_jst()
    daily_threads = state.setdefault("daily_threads", {})

    if day in daily_threads and daily_threads[day].get("thread_ts"):
        return daily_threads[day]["thread_ts"]

    text = f"📌 今日のQuestion（{day}）\nこのスレッドに今日の回答をまとめます。"
    msg = slack_post(
        "chat.postMessage",
        {
            "channel": CHANNEL_ID,
            "text": text,
        },
    )
    thread_ts = msg["ts"]
    daily_threads[day] = {"thread_ts": thread_ts}
    save_state(state)
    return thread_ts


def get_user_icon(user_id: str):
    info = slack_get("users.info", {"user": user_id})
    profile = info.get("user", {}).get("profile", {})
    return profile.get("image_192") or profile.get("image_72") or profile.get("image_512")


def find_reply(dm_id: str, user_id: str, thread_ts: str):
    """
    DMの質問メッセージに対するスレッド返信のみ拾う。
    """
    res = slack_get(
        "conversations.replies",
        {"channel": dm_id, "ts": str(thread_ts), "limit": 200},
    )

    # messages[0] が親（質問）
    for m in res.get("messages", [])[1:]:
        if m.get("user") == user_id and m.get("text"):
            return m["text"]

    return None


def post_answer_in_thread(parent_thread_ts: str, question: str, answerer_user_id: str, answer_text: str):
    icon_url = get_user_icon(answerer_user_id)

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Q.* {question}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*<@{answerer_user_id}> の回答*"}
        }
    ]

    if icon_url:
        blocks.append({
            "type": "image",
            "image_url": icon_url,
            "alt_text": "answerer icon"
        })

    quoted_answer = answer_text.replace("\n", "\n> ")
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"> {quoted_answer}"}
    })

    slack_post(
        "chat.postMessage",
        {
            "channel": CHANNEL_ID,
            "thread_ts": parent_thread_ts,
            "text": f"Q: {question} / <@{answerer_user_id}> の回答",
            "blocks": blocks,
        },
    )


def main():
    state = load_state()
    pending = state.get("pending", [])

    print("pending count:", len(pending))

    if not pending:
        print("No pending.")
        return

    new_pending = []
    parent_thread_ts = None

    for p in pending:
        user = p["user"]
        dm = p["dm"]
        q = p["question"]
        thread_ts = p.get("thread_ts")

        if not thread_ts:
            print("missing thread_ts, keep pending:", user)
            new_pending.append(p)
            continue

        print("checking:", "user", user, "dm", dm, "thread_ts", thread_ts)

        answer = find_reply(dm, user, thread_ts)
        print("answer found:", bool(answer))

        if answer:
            if parent_thread_ts is None:
                parent_thread_ts = ensure_daily_parent_post(state)

            post_answer_in_thread(parent_thread_ts, q, user, answer)
            print("posted to parent thread")
        else:
            new_pending.append(p)

    state["pending"] = new_pending
    save_state(state)
    print("done")


if __name__ == "__main__":
    main()
