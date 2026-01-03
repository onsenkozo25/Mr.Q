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


def get_user_icon(user_id: str):
    # users:read が必要（あなたは既に付与済みのはず）
    info = slack_get("users.info", {"user": user_id})
    profile = info.get("user", {}).get("profile", {})
    return profile.get("image_192") or profile.get("image_72") or profile.get("image_512")



def find_reply(dm_id: str, user_id: str, thread_ts: str):
    """
    DMの「スレッド返信」でユーザー回答を受け取る前提。
    thread_ts は botが送った質問メッセージの ts（=スレッド親）。
    """
    res = slack_get(
        "conversations.replies",
        {"channel": dm_id, "ts": str(thread_ts), "limit": 200},
    )

    # messages[0] が親（質問）。messages[1:] が返信。
    for m in res.get("messages", [])[1:]:
        if m.get("user") == user_id and m.get("text"):
            return m["text"]

    return None


def post_pretty(channel_id: str, question: str, answerer_user_id: str, answer_text: str):
    icon_url = get_user_icon(answerer_user_id)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": question, "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*<@{answerer_user_id}> の回答*"},
        },
    ]

    # “拡大アイコン”っぽく見せる：画像ブロック（Slack側で大きめに表示される）
    if icon_url:
        blocks.append(
            {"type": "image", "image_url": icon_url, "alt_text": "answerer icon"}
        )

    # 回答を引用表示（左に縦線）
    quoted_answer = answer_text.replace("\n", "\n> ")
    blocks.append(
        {"type": "section", "text": {"type": "mrkdwn", "text": f"> {quoted_answer}"}}
    )

    slack_post(
        "chat.postMessage",
        {
            "channel": channel_id,
            # フォールバック（通知/検索用）
            "text": f"{question} / <@{answerer_user_id}> の回答",
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

    for p in pending:
        user = p["user"]
        dm = p["dm"]
        q = p["question"]
        thread_ts = p.get("thread_ts")

        if not thread_ts:
            # 古い形式が混ざってたら残す（または捨てる）
            print("missing thread_ts, keep pending:", user)
            new_pending.append(p)
            continue

        print("checking:", "user", user, "dm", dm, "thread_ts", thread_ts)

        answer = find_reply(dm, user, thread_ts)
        print("answer found:", bool(answer))

        if answer:
            post_pretty(CHANNEL_ID, q, user, answer)
            print("posted to channel")
        else:
            new_pending.append(p)

    state["pending"] = new_pending
    save_state(state)
    print("done")


if __name__ == "__main__":
    main()
