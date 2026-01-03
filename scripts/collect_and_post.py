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


def get_user_icon(user_id: str):
    # users:read が必要（あなたは既に持ってる）
    info = slack_get("users.info", {"user": user_id})
    profile = info.get("user", {}).get("profile", {})
    # 画像URLはいくつかサイズがある。512が綺麗
    return profile.get("image_512") or profile.get("image_192") or profile.get("image_72")

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
           icon_url = get_user_icon(user)

blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": f"{q}", "emoji": True}},
    {"type": "section", "text": {"type": "mrkdwn", "text": f"*<@{user}> の回答*"}},
]

# “拡大アイコン”っぽく見せる：画像ブロック（大きめに表示される）
if icon_url:
    blocks.append({
        "type": "image",
        "image_url": icon_url,
        "alt_text": "answerer icon"
    })

# 回答は“引用”っぽく見せる（縦線表示）
blocks.append({
    "type": "section",
    "text": {"type": "mrkdwn", "text": f"> {answer.replace('\n', '\n> ')}"}
})

slack_post("chat.postMessage", {
    "channel": CHANNEL_ID,
    "text": f"{q} / <@{user}> の回答: {answer}",  # 通知/検索用のフォールバック
    "blocks": blocks
})

        else:
            new_pending.append(p)


    state["pending"] = new_pending
    save_state(state)
    print("done")


if __name__ == "__main__":
    main()
