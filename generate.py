# Builds config.json which is a list of links that support TV streaming natively from FMHY. 
#
# Run it with no arguments to write config.json. Pass --check to do all the work and write
# nothing, which is what you want before a push. Pass --out NAME to write somewhere else. It needs
# nothing but the standard library.
#
# It runs unattended every night at 5am UTC based on the github action

import concurrent.futures
import json
import re
import socket
import sys
import urllib.error
import urllib.request

CATEGORIES = [
    {
        "name": "English Movies & Shows",
        "items": ["CinemaOS", "NoirX", "Cineby", "Fmovies+", "Flixer", "MeowTV", "FlickyStream", "BingeBox"],
    },
    {
        "name": "Desi Movies",
        "items": ["MultiMovies", "Desicinemas", "67Movies", "456movie"],
    },
    {
        "name": "Desi Shows",
        "items": ["Desi Serials"],
    },
    {
        "name": "Anime",
        "items": ["Miruro", "AnimeX", "Yenime", "Anidap", "Mkissa", "Kuroiru"],
    },
    {
        "name": "Live TV",
        "items": ["EasyWebTV", "Famelack", "DaddyLive TV"],
    },
    {
        "name": "Live Sports",
        "items": ["Streamed", "StreamSports99", "SportsBite TV", "StreamFree", "DaddyLive"],
    },
    {
        "name": "Sports Replay",
        "items": ["StreamSports99", "EasyWebTV", "Famelack", "DaddyLive TV"],
    },
]

WIKI = "https://raw.githubusercontent.com/wiki/fmhy/FMHY/%s.md"
PAGES = ["Streaming", "Non-Eng"]
UA = "Mozilla/5.0 (Android 14; Mobile; rv:152.0) Gecko/152.0 Firefox/152.0"
CONNECT_TIMEOUT = 6
FETCH_TIMEOUT = 20

LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
HEADING = re.compile(r"^(#{1,4})\s+(.*)")
INLINE_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
DECORATION = re.compile(r"[⁠​‌‍►▷▶◄#*⭐]")
JUNK_URL = re.compile(r"discord|t\.me|telegram|/wiki/|rentry|status|\.link|/mirror|github\.com|reddit\.com", re.I)
MIRROR = re.compile(r"^(?:\d+|mirrors?|backup|official)$", re.I)
HELPER = re.compile(r"bypass|vpns?|schedule|guide|proxy|unblock|discord|telegram|status|invite|how to|extension", re.I)


def die(message):
    print("ERROR: " + message, file=sys.stderr)
    sys.exit(1)


def warn(message):
    print("warning: " + message, file=sys.stderr)


def tidy(text):
    return DECORATION.sub("", INLINE_LINK.sub(r"\1", text)).strip()


def name_of(text):
    return DECORATION.sub("", text).strip()


def get_page(page):
    url = WIKI % page
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            return response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as error:
        die("could not load %s: %s" % (url, error))


def scan(text):
    sections = {}
    chains = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        heading = HEADING.match(line)
        if heading:
            current = sections.setdefault(tidy(heading.group(2)), []) if len(heading.group(1)) == 2 else None
            continue
        links = list(LINK.finditer(line))
        if not links:
            continue
        sources = []
        for match in links:
            url = match.group(2)
            if JUNK_URL.search(url):
                continue
            label = name_of(match.group(1))
            key = label.lower()
            if MIRROR.match(key):
                if sources:
                    sources[-1][1].append(url)
                continue
            if HELPER.search(key) or len(key) < 3:
                continue
            sources.append([label, [url]])
        starred = "⭐" in line
        for label, urls in sources:
            merged = chains.setdefault(label.lower(), [])
            for url in urls:
                clean = url.rstrip("/")
                if clean not in merged:
                    merged.append(clean)
            if starred and current is not None and label not in current:
                current.append(label)
    return sections, chains


def load_pages():
    sections = {}
    chains = {}
    for page in PAGES:
        page_sections, page_chains = scan(get_page(page))
        for heading, names in page_sections.items():
            merged = sections.setdefault(heading, [])
            for name in names:
                if name not in merged:
                    merged.append(name)
        for key, urls in page_chains.items():
            merged = chains.setdefault(key, [])
            for url in urls:
                if url not in merged:
                    merged.append(url)
    return sections, chains


def resolve(entry, chains, where):
    if entry.startswith("http"):
        return [entry.rstrip("/")]
    key = entry.strip().lower()
    if key in chains:
        return list(chains[key])
    warn("'%s' (in %s) is not on FMHY right now, skipping it" % (entry, where))
    return []


def build(sections, chains):
    cats = []
    for category in CATEGORIES:
        name = category["name"]
        items = []
        if "items" in category:
            for entry in category["items"]:
                urls = resolve(entry, chains, name)
                if not urls:
                    continue
                label = entry if not entry.startswith("http") else entry.split("://")[1].split("/")[0]
                items.append({"name": label, "urls": urls})
        elif "from" in category:
            found = sections.get(category["from"])
            if found is None:
                die("FMHY section '%s' for category '%s' is gone" % (category["from"], name))
            for source_name in found:
                urls = chains.get(source_name.lower())
                if urls:
                    items.append({"name": source_name, "urls": list(urls)})
        else:
            die("category '%s' has neither items nor from" % name)
        if not items:
            die("category '%s' came out empty" % name)
        cats.append({"name": name, "items": items})
    return cats


def reachable(url):
    try:
        host = url.split("://", 1)[1].split("/", 1)[0]
        port = 443 if url.startswith("https") else 80
        if ":" in host:
            host, text_port = host.rsplit(":", 1)
            port = int(text_port)
        with socket.create_connection((host, port), CONNECT_TIMEOUT):
            return True
    except (OSError, ValueError, IndexError):
        return False


def deadcheck(cats):
    urls = {url for c in cats for item in c["items"] for url in item["urls"]}
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        live = dict(zip(urls, pool.map(reachable, urls)))
    down = 0
    for category in cats:
        for item in category["items"]:
            item["urls"].sort(key=lambda url: not live[url])
            down += sum(1 for url in item["urls"] if not live[url])
    return len(urls), down


def main():
    args = sys.argv[1:]
    check_only = "--check" in args
    out = args[args.index("--out") + 1] if "--out" in args else "config.json"

    sections, chains = load_pages()
    cats = build(sections, chains)
    total, down = deadcheck(cats)

    items = sum(len(c["items"]) for c in cats)
    print("%d categories, %d items, %d urls, %d not answering" % (len(cats), items, total, down))
    for category in cats:
        print("  %-24s %d items" % (category["name"], len(category["items"])))
        for item in category["items"]:
            if len(item["urls"]) > 1:
                print("      %-16s chain of %d" % (item["name"], len(item["urls"])))

    if not check_only:
        json.dump({"cats": cats}, open(out, "w"), separators=(",", ":"))
        print("wrote " + out)


main()
