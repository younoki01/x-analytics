import os
import requests
from datetime import datetime, timedelta, timezone

# ── 環境変数 ──────────────────────────────────────────────
X_BEARER_TOKEN    = os.environ["X_BEARER_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))
USER_ID = "1957292180013236224"  # @Y0shiCareer

# ── X API: 前日のツイートを取得 ───────────────────────────
def get_yesterday_tweets():
    yesterday_start = datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    yesterday_end   = datetime(2026, 3, 17, 23, 59, 59, tzinfo=timezone.utc)

    url = f"https://api.twitter.com/2/users/{USER_ID}/tweets"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    params = {
        "start_time": yesterday_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time":   yesterday_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tweet.fields": "public_metrics,created_at,text,in_reply_to_user_id",
        "max_results": 100,
    }
    r = requests.get(url, headers=headers, params=params)
    print(f"  X API status: {r.status_code}")
    print(f"  X API response: {r.text[:500]}")  # ← 追加
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
1. ?? 昨日のサマリー（投稿数・合計エンゲージメント）
2. ?? 最もパフォーマンスが高かった投稿とその理由
3. ?? 気づいたパターンやインサイト（2?3点）
4. ?? 明日に向けたアクションアドバイス（1?2点）

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
    text = f"*?? X 日次エンゲージメントレポート（{today}）*\n\n{analysis}"
    payload = {"text": text}
    r = requests.post(SLACK_WEBHOOK_URL, json=payload)
    r.raise_for_status()
    print(f"? Slack通知送信完了（対象ツイート数: {tweet_count}）")

# ── メイン ────────────────────────────────────────────────
def main():
    print("? X日次分析ツール 起動")
    tweets = get_yesterday_tweets()
    print(f"  取得ツイート数: {len(tweets)}")
    analysis = analyze_with_claude(tweets)
    send_to_slack(analysis, len(tweets))

if __name__ == "__main__":
    main()