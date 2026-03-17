import os
import json
import requests
from datetime import datetime, timedelta, timezone

# ── 環境変数 ──────────────────────────────────────────────
X_BEARER_TOKEN      = os.environ["X_BEARER_TOKEN"]
X_API_KEY           = os.environ["X_API_KEY"]
X_API_SECRET        = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN      = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET     = os.environ["X_ACCESS_SECRET"]
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
SLACK_WEBHOOK_URL   = os.environ["SLACK_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))

# ── X API: 自分のユーザーIDを取得 ─────────────────────────
def get_user_id():
    url = "https://api.twitter.com/2/users/me"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["data"]["id"]

# ── X API: 前日のツイートを取得 ───────────────────────────
def get_yesterday_tweets(user_id: str):
    now = datetime.now(JST)
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end   = yesterday_start.replace(hour=23, minute=59, second=59)

    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    params = {
        "start_time": yesterday_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time":   yesterday_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tweet.fields": "public_metrics,created_at,in_reply_to_user_id,text",
        "max_results": 100,
    }
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json().get("data", [])

# ── Claude API: エンゲージメント分析 ──────────────────────
def analyze_with_claude(tweets: list) -> str:
    if not tweets:
        return "昨日の投稿はありませんでした。"

    tweet_summary = "\n".join([
        f"- [{t['created_at']}] {t['text'][:80]}{'...' if len(t['text'])>80 else ''}\n"
        f"  いいね:{t['public_metrics']['like_count']} RT:{t['public_metrics']['retweet_count']} "
        f"リプライ:{t['public_metrics']['reply_count']} インプレッション:{t['public_metrics']['impression_count']}"
        for t in tweets
    ])

    prompt = f"""以下は昨日のXへの投稿データです。エンゲージメントを分析して日本語で報告してください。

{tweet_summary}

以下の形式で回答してください：
1. $D83D$DCCA 昨日のサマリー（投稿数・合計エンゲージメント）
2. $D83C$DFC6 最もパフォーマンスが高かった投稿とその理由
3. $D83D$DCA1 気づいたパターンやインサイト（2$301C3点）
4. $D83D$DE80 明日に向けたアクションアドバイス（1$301C2点）

簡潔かつ実用的に、箇条書きで答えてください。"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
    r.raise_for_status()
    return r.json()["content"][0]["text"]

# ── Slack通知 ─────────────────────────────────────────────
def send_to_slack(analysis: str, tweet_count: int):
    today = datetime.now(JST).strftime("%Y/%m/%d")
    text = f"*$D83D$DCC8 X 日次エンゲージメントレポート（{today}）*\n\n{analysis}"
    payload = {"text": text}
    r = requests.post(SLACK_WEBHOOK_URL, json=payload)
    r.raise_for_status()
    print(f"$2705 Slack通知送信完了（対象ツイート数: {tweet_count}）")

# ── メイン ────────────────────────────────────────────────
def main():
    print("? X日次分析ツール 起動")
    user_id = "1957292180013236224"  # @Y0shiCareer
    print(f"  ユーザーID: {user_id}")

    tweets = get_yesterday_tweets(user_id)
    print(f"  取得ツイート数: {len(tweets)}")

    analysis = analyze_with_claude(tweets)
    send_to_slack(analysis, len(tweets))

if __name__ == "__main__":
    main()
