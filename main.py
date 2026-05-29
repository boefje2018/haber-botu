import asyncio
import json
import re
import feedparser
import httpx
from datetime import datetime


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def clean_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:300]


def fetch_feed(url: str) -> list:
    try:
        feed = feedparser.parse(url)
        entries = []
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = clean_html(entry.get("summary", entry.get("description", "")))
            pub_date = entry.get("published", "")
            if title:
                entries.append({"title": title, "link": link, "summary": summary, "date": pub_date})
        return entries
    except:
        return []


def format_category(entries: list, label: str) -> str:
    lines = [f"<b>{label}</b>\n"]
    for e in entries[:3]:
        lines.append(f"<b>{e['title']}</b>")
        if e["summary"][:80]:
            lines.append(f"{e['summary'][:80]}...")
        lines.append(f"<a href='{e['link']}'>Detay</a>\n")
    return "\n".join(lines)


def format_kusadasi(all_entries: list) -> str:
    unique = []
    seen = set()
    for e in all_entries:
        if e["title"] not in seen:
            seen.add(e["title"])
            unique.append(e)
    lines = ["<b>📍 KUŞADASI HABER</b>\n"]
    for e in unique[:5]:
        lines.append(f"<b>{e['title']}</b>")
        if e["summary"][:100]:
            lines.append(f"{e['summary'][:100]}...")
        lines.append(f"<a href='{e['link']}'>Detay</a>\n")
    return "\n".join(lines)


async def send_telegram(bot_token: str, chat_id: str, message: str):
    if not chat_id:
        return False
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
        )
    return r.status_code == 200


async def run_categories(config, bot_token):
    for category, feeds in config["feeds"].items():
        channel = config["telegram"]["channels"].get(category)
        if not channel or not channel.get("id"):
            continue
        chat_id = channel["id"]
        label = channel.get("label", category.upper())
        all_entries = []
        for feed_url in feeds or []:
            all_entries.extend(fetch_feed(feed_url))
        if not all_entries:
            print(f"  {label}: haber yok")
            continue
        unique = []
        seen = set()
        for e in all_entries:
            if e["title"] not in seen:
                seen.add(e["title"])
                unique.append(e)
        if not unique:
            continue
        msg = format_category(unique[:3], label)
        ok = await send_telegram(bot_token, chat_id, msg)
        print(f"{'✅' if ok else '❌'} {label} -> {channel['channel']} ({len(unique[:3])} haber)")


async def run_kusadasi(config, bot_token):
    ks = config.get("kusadasi")
    if not ks or not ks.get("enabled"):
        return
    chat_id = ks.get("channel_id")
    if not chat_id:
        return
    all_entries = []
    for feed in ks.get("feeds", []):
        entries = fetch_feed(feed["url"])
        all_entries.extend(entries)
    if not all_entries:
        print(f"  Kuşadası: haber yok")
        return
    msg = format_kusadasi(all_entries)
    ok = await send_telegram(bot_token, chat_id, msg)
    print(f"{'✅' if ok else '❌'} Kuşadası -> {ks.get('channel_name','?')} (toplam haber)")


async def run_once():
    config = load_config()
    bot_token = config["telegram"].get("bot_token", "")
    if not bot_token:
        print("❌ Bot token yok")
        return
    print(f"[{datetime.now().strftime('%d.%m.%Y %H:%M')}] Başlatıldı")
    await run_categories(config, bot_token)
    await run_kusadasi(config, bot_token)
    print(f"[{datetime.now().strftime('%d.%m.%Y %H:%M')}] Tamamlandi\n")


def main():
    import sys
    args = set(sys.argv[1:])
    config = load_config()
    bot_token = config["telegram"].get("bot_token", "")
    if not bot_token:
        print("❌ Bot token yok")
        return

    run_cats = not args or "--categories" in args
    run_ks = not args or "--kusadasi" in args

    async def run():
        print(f"[{datetime.now().strftime('%d.%m.%Y %H:%M')}] Başlatıldı")
        if run_cats:
            await run_categories(config, bot_token)
        if run_ks:
            await run_kusadasi(config, bot_token)
        print(f"[{datetime.now().strftime('%d.%m.%Y %H:%M')}] Tamamlandi\n")

    asyncio.run(run())


if __name__ == "__main__":
    main()
