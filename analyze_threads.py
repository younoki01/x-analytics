import os
import requests
from datetime import datetime, timedelta, timezone

THREADS_ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
ANTHROPIC_API_KEY    = os.environ["ANTHROPIC_API_KEY"]
SLACK_WEBHOOK_URL    = os.environ["SLACK_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))

# ── Threads API: 前日の投稿を取得 ─────────────────────────
def get_yesterday_threads():
    now = datetime.now(JST)
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end   = yesterday_start.replace(hour=23, minute=59, second=59)

    url = "https://graph.threads.net/v1.0/me/threads"
    params = {
        "fields": "id,text,timestamp,like_count,replies_count,repost_count,quote_count",
        "since": int(yesterday_start.astimezone(timezone.utc).timestamp()),
        "until": int(yesterday_end.astimezone(timezone.utc).timestamp()),
        "access_token": THREADS_ACCESS_TOKEN,
        "limit": 100,
    }
    r = requests.get(url, params=params)
    print(f"Threads API status: {r.status_code}")
    r.raise_for_status()
    posts = r.json().get("data", [])
    print(f"取得投稿数: {len(posts)}")

    # 各投稿のインサイトを個別取得
    for post in posts:
        post_id = post["id"]
        insight_url = f"https://graph.threads.net/v1.0/{post_id}/insights"
        insight_params = {
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": THREADS_ACCESS_TOKEN,
        }
        ri = requests.get(insight_url, params=insight_params)
        if ri.status_code == 200:
            data = ri.json().get("data", [])
            for metric in data:
                name = metric.get("name")
                value = metric.get("values", [{}])[0].get("value", 0)
                post[f"insight_{name}"] = value
            print(f"  投稿 {post_id}: views={post.get('insight_views',0)}, likes={post.get('insight_likes',0)}")
        else:
            print(f"  インサイト取得失敗 {post_id}: {ri.status_code} {ri.text[:100]}")

    return posts

# ── Claude API: 分析 ──────────────────────────────────────
def analyze_with_claude(posts: list) -> str:
    if not posts:
        return "昨日のThreads投稿はありませんでした。"

    post_summary = "\n".join([
        f"- [{p.get('timestamp','')}] {p.get('text','')[:80]}{'...' if len(p.get('text',''))>80 else ''}\n"
        f"  閲覧:{p.get('insight_views',0)} いいね:{p.get('insight_likes',0)} "
        f"返信:{p.get('insight_replies',0)} リポスト:{p.get('insight_reposts',0)}"
        for p in posts
    ])

    total_views   = sum(p.get('insight_views', 0) or 0 for p in posts)
    total_likes   = sum(p.get('insight_likes', 0) or 0 for p in posts)
    total_replies = sum(p.get('insight_replies', 0) or 0 for p in posts)

    prompt = f"""以下は昨日のThreads投稿データです。エンゲージメントを分析して日本語で報告してください。

【全体集計】
- 投稿数: {len(posts)}件
- 合計閲覧数: {total_views:,}
- 合計いいね: {total_likes}
- 合計返信: {total_replies}

【投稿一覧】
{post_summary}

以下の形式で回答してください：
1. 📊 昨日のサマリー（投稿数・エンゲージメント総評）
2. 🏆 最もパフォーマンスが高かった投稿とその理由
3. 💡 気づいたパターンやインサイト（2〜3点）
4. 🚀 明日に向けたアクションアドバイス（1〜2点）

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
def send_to_slack(analysis: str, post_count: int):
    today = datetime.now(JST).strftime("%Y/%m/%d")
    text = f"*🧵 Threads 日次エンゲージメントレポート（{today}）*\n\n{analysis}"
    payload = {"text": text}
    r = requests.post(SLACK_WEBHOOK_URL, json=payload)
    r.raise_for_status()
    print(f"✅ Slack通知送信完了（対象投稿数: {post_count}）")

# ── メイン ────────────────────────────────────────────────
def main():
    print("▶ Threads日次分析ツール 起動")
    posts = get_yesterday_threads()
    analysis = analyze_with_claude(posts)
    send_to_slack(analysis, len(posts))

if __name__ == "__main__":
    main()
