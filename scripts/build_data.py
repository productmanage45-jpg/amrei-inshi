#!/usr/bin/env python3
"""
Builds data/sayings.json: every place in Talmud Bavli where a popular saying is
quoted ("אמרי אינשי", "מתלא", "משל הדיוט", ...), plus data/review.json for checking.

Three checks so nothing is missed:
  1. Full scan of Shas (Sefaria, William Davidson Aramaic). EVERY match in a line
     is kept, not just the first.
  2. Rescan of every amud in a second edition (Vilna text from Wikisource, on
     Sefaria). Anything only that edition catches is added and flagged.
  3. Every source is fetched again on its own to confirm the saying is there.
     Separately, every line with אינשי / מתל / הדיוט / בריות etc. that no marker
     caught is listed in review.json so a person can look at it.

Run by the GitHub Action, or locally:  python3 scripts/build_data.py
"""
import json, re, time, html, datetime, pathlib, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

V3 = "https://www.sefaria.org/api/v3/texts/"
V1 = "https://www.sefaria.org/api/texts/"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sayings.json"
REVIEW = ROOT / "data" / "review.json"
PRIMARY = "William Davidson Edition - Aramaic"
SECOND = "Wikisource Talmud Bavli"

BAVLI = [
    ("סדר זרעים", [("Berakhot", "ברכות")]),
    ("סדר מועד", [("Shabbat", "שבת"), ("Eruvin", "עירובין"), ("Pesachim", "פסחים"),
                  ("Rosh Hashanah", "ראש השנה"), ("Yoma", "יומא"), ("Sukkah", "סוכה"),
                  ("Beitzah", "ביצה"), ("Taanit", "תענית"), ("Megillah", "מגילה"),
                  ("Moed Katan", "מועד קטן"), ("Chagigah", "חגיגה")]),
    ("סדר נשים", [("Yevamot", "יבמות"), ("Ketubot", "כתובות"), ("Nedarim", "נדרים"),
                  ("Nazir", "נזיר"), ("Sotah", "סוטה"), ("Gittin", "גיטין"), ("Kiddushin", "קידושין")]),
    ("סדר נזיקין", [("Bava Kamma", "בבא קמא"), ("Bava Metzia", "בבא מציעא"), ("Bava Batra", "בבא בתרא"),
                    ("Sanhedrin", "סנהדרין"), ("Makkot", "מכות"), ("Shevuot", "שבועות"),
                    ("Avodah Zarah", "עבודה זרה"), ("Horayot", "הוריות")]),
    ("סדר קדשים", [("Zevachim", "זבחים"), ("Menachot", "מנחות"), ("Chullin", "חולין"),
                   ("Bekhorot", "בכורות"), ("Arakhin", "ערכין"), ("Temurah", "תמורה"),
                   ("Keritot", "כריתות"), ("Meilah", "מעילה"), ("Tamid", "תמיד")]),
    ("סדר טהרות", [("Niddah", "נדה")]),
]

# Phrases that introduce a popular saying. B = start of a word, allowing the
# one-letter prefixes ד/ו/כ/ה/ל/ש/ב/מ in front.
B = r"(?<![א-ת])(?:אד|[דוכהלשבמ]{0,3})"
E = r"(?![א-ת])"
MARKERS = [
    ("אמרי אינשי", rf"{B}(?:אמרי|אמרין)\s+(?:אינשי|אינשין|אנשי|אינישי){E}|{B}אמרו\s+(?:אינשי|אינשין){E}|{B}אינשי\s+אמרי{E}(?!\s+(?:ליה|להו|לה|לי)(?![א-ת]))"),
    ("מתלא", rf"{B}(?:מתלא|מתלי|מתליה){E}"),
    ("משל הדיוט", rf"{B}משל\s+(?:ה)?הדיוט{E}"),
    ("בני נשא", rf"{B}(?:אמרי|אמרין)\s+בני\s+נשא{E}|{B}בני\s+נשא\s+אמרי{E}"),
    ("הבריות אומרות", rf"{B}(?:אומרים|אומרות|אמרו|אמרי)\s+(?:ה)?בריות{E}|{B}הבריות\s+(?:אומרים|אומרות){E}"),
]
MARKER_RE = re.compile("|".join(f"(?P<m{i}>{p})" for i, (_, p) in enumerate(MARKERS)))
# Words that often sit near a saying. Lines with these that no marker caught go to review.
NEAR_RE = re.compile(r"\S*אמר\S*\s+(?:\S+\s+)?\S*אינש\S*|\S*אינש\S*\s+(?:\S+\s+)?\S*אמר\S*|(?<![א-ת])[דוכ]?מתל[אי](?![א-ת])|פתגמ|משל\S*\s+(?:\S+\s+){0,2}\S*הדיוט|בני\s+נשא|(?:אומרים|אומרות)\s+(?:בני\s+אדם|הבריות)|בני\s+אדם\s+אומרים|כמו\s+שאומרים")
# Checked by hand: the marker words appear but no saying is quoted.
EXCLUDE = {
    "Yoma 78b:5",         # אמרי אינשי עבדו ליה = "people will say they did it", not a saying
    "Bava Batra 59b:5",   # למתלא ביה = to hang something
    "Chullin 10b:4",      # במאי מתלא תלינן = what do we attribute it to
    "Niddah 4a:13",       # same
    "Sanhedrin 38b:22",   # תילתא מתלי = a third parables (R' Meir's teaching)
}

NIKUD = re.compile(r"[֑-ֽֿ-ׇ]")
FOOTNOTE = re.compile(r'<sup[^>]*class="footnote-marker"[^>]*>.*?</sup>|<i[^>]*class="footnote"[^>]*>.*?</i>', re.S)
TAGS = re.compile(r"<[^>]+>")
PARENS = re.compile(r"\([^)]{0,40}\)")  # Wikisource verse refs, e.g. (ישעיהו מט, י)


def clean(s):
    s = FOOTNOTE.sub("", s or "")
    s = html.unescape(TAGS.sub("", s)).replace("־", " ")
    return re.sub(r"\s+", " ", NIKUD.sub("", s)).strip()


def get(url):
    for i in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "amrei-inshi-site/2.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception:
            if i == 5:
                raise
            time.sleep(3 * (i + 1))


def get_book(title):
    q = "?version=" + urllib.parse.quote("hebrew|" + PRIMARY) + "&version=" + urllib.parse.quote("hebrew|" + SECOND)
    d = get(V3 + urllib.parse.quote(title.replace(" ", "_")) + q)
    vers = {v["versionTitle"]: v.get("text") or [] for v in d.get("versions", [])}
    return vers.get(PRIMARY, []), vers.get(SECOND, [])


def amud(i):
    """Index in Sefaria's Talmud array -> '2a', '2b', ..."""
    return f"{i // 2 + 1}{'ab'[i % 2]}"


def url_for(ref):
    return "https://www.sefaria.org/" + urllib.parse.quote(ref.replace(" ", "_")) + "?lang=he"


def find(text):
    """Every marker match in a line: [(marker name, match)]."""
    out = []
    for m in MARKER_RE.finditer(text):
        k = next(i for i, g in enumerate(m.groups()) if g is not None)
        out.append((MARKERS[k][0], m))
    return out


def excerpt(text, m):
    start = text.rfind(" ", 0, m.start()) + 1
    before = text[:start].split()
    if before and before[-1].strip(".,:") in ("היינו", "והיינו", "הוא", "הדא"):
        start = text.rfind(before[-1], 0, start)
    out = []
    for w in text[start:].split():
        out.append(w)
        if len(out) > 2 and (w.endswith(":") or w.endswith(".") or len(out) >= 28):
            break
    return " ".join(out)


def he_ref(he_title, i, seg=None):
    return f"{he_title} {heb_num(i // 2 + 1)}{'.:'[i % 2]}"


def heb_num(n):
    ones = "אבגדהוזחט"
    tens = "יכלמנסעפצ"
    hund = "קרשת"
    s = ""
    while n >= 400:
        s += "ת"; n -= 400
    if n >= 100:
        s += hund[n // 100 - 1]; n %= 100
    if n == 15:
        return s + "טו"
    if n == 16:
        return s + "טז"
    if n >= 10:
        s += tens[n // 10 - 1]; n %= 10
    if n:
        s += ones[n - 1]
    return s


def scan_book(title, he, group, primary, second):
    items, review = [], []
    for i in range(max(len(primary), len(second))):
        p_amud = [clean(x) for x in (primary[i] if i < len(primary) else []) if isinstance(x, str)]
        s_amud = [clean(PARENS.sub("", x)) for x in (second[i] if i < len(second) else []) if isinstance(x, str)]
        p_count = {}
        # Pass 1: every match in every line of the primary edition
        for j, t in enumerate(p_amud, 1):
            ref = f"{title} {amud(i)}:{j}"
            hits = find(t)
            for n, (name, m) in enumerate(hits, 1):
                p_count[name] = p_count.get(name, 0) + 1
                if ref in EXCLUDE:
                    continue  # counted, so the Vilna pass doesn't re-add it
                items.append({
                    "ref": ref, "heRef": he_ref(he, i, j), "url": url_for(ref),
                    "marker": name, "n": n, "excerpt": excerpt(t, m), "text": t,
                    "edition": "primary",
                })
            if not hits and NEAR_RE.search(t):
                review.append({"ref": ref, "url": url_for(ref), "edition": PRIMARY, "text": t})
        # Pass 2: the second edition, amud by amud
        s_count = {}
        for j, t in enumerate(s_amud, 1):
            ref = f"{title} {amud(i)}:{j}"
            hits = find(t)
            for name, m in hits:
                s_count[name] = s_count.get(name, 0) + 1
                if s_count[name] > p_count.get(name, 0):
                    # Only the second edition has this one: add it, flagged
                    items.append({
                        "ref": f"{title} {amud(i)}", "heRef": he_ref(he, i, j), "url": url_for(f"{title} {amud(i)}"),
                        "marker": name, "n": 1, "excerpt": excerpt(t, m), "text": t,
                        "edition": "second", "flag": "only-in-vilna",
                    })
        for name, c in p_count.items():
            if c > s_count.get(name, 0) and second and i < len(second) and second[i]:
                for it in items:
                    if it["ref"].startswith(f"{title} {amud(i)}:") and it["marker"] == name:
                        it["flag"] = "not-in-vilna"
    print(f"{title}: {len(items)} sayings, {len(review)} to review", flush=True)
    return {"id": title, "he": he, "corpus": "bavli", "group": group, "items": items}, review


def verify(item):
    """Pass 3: fetch the source on its own and make sure the saying is there."""
    try:
        ed = PRIMARY if item.get("edition") == "primary" else SECOND
        d = get(V3 + urllib.parse.quote(item["ref"].replace(" ", "_")) + "?version=" + urllib.parse.quote("hebrew|" + ed))
        texts = [x for v in d.get("versions", []) for x in _flat(v.get("text"))]
        joined = " ".join(clean(PARENS.sub("", x)) for x in texts)
        return bool(MARKER_RE.search(joined))
    except Exception:
        return None


def _flat(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for y in x:
            yield from _flat(y)


def main():
    jobs = [(t, h, g) for g, books in BAVLI for t, h in books]
    books, review, failed = [], [], []
    for t, h, g in jobs:
        try:
            p, s = get_book(t)
            b, r = scan_book(t, h, g, p, s)
            books.append(b); review += r
        except Exception as e:
            print(f"FAILED {t}: {e}", flush=True)
            failed.append(t)
            books.append({"id": t, "he": h, "corpus": "bavli", "group": g, "items": []})
        time.sleep(0.3)

    all_items = [it for b in books for it in b["items"]]
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(verify, all_items))
    for it, ok in zip(all_items, results):
        it["verified"] = ok
    bad = [it for it in all_items if it["verified"] is not True]

    gen = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": gen, "source": "Sefaria.org", "editions": [PRIMARY, SECOND],
        "books": books,
    }, ensure_ascii=False, indent=1), "utf-8")
    REVIEW.write_text(json.dumps({
        "generated": gen,
        "failed_books": failed,
        "only_in_vilna": [it for it in all_items if it.get("flag") == "only-in-vilna"],
        "not_in_vilna": [it for it in all_items if it.get("flag") == "not-in-vilna"],
        "not_verified": bad,
        "near_misses": review,
    }, ensure_ascii=False, indent=1), "utf-8")
    print(f"total: {len(all_items)} | only in Vilna: {sum(1 for i in all_items if i.get('flag') == 'only-in-vilna')}"
          f" | not verified: {len(bad)} | near misses: {len(review)} | failed books: {failed}")


if __name__ == "__main__":
    main()
