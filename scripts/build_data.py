#!/usr/bin/env python3
"""
Builds data/sayings.json: every place in Talmud Bavli (and Midrash) where a
popular saying is quoted ("אמרי אינשי", "מתלא", "משל הדיוט", ...).
Text comes from the Sefaria API. Run by the GitHub Action, or locally:
    python3 scripts/build_data.py
"""
import json, re, time, html, datetime, pathlib, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

API = "https://www.sefaria.org/api/texts/"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "sayings.json"

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
MIDRASH = [
    ("מדרש רבה", [("Bereshit Rabbah", "בראשית רבה"), ("Shemot Rabbah", "שמות רבה"),
                  ("Vayikra Rabbah", "ויקרא רבה"), ("Bamidbar Rabbah", "במדבר רבה"),
                  ("Devarim Rabbah", "דברים רבה"), ("Shir HaShirim Rabbah", "שיר השירים רבה"),
                  ("Ruth Rabbah", "רות רבה"), ("Eichah Rabbah", "איכה רבה"),
                  ("Kohelet Rabbah", "קהלת רבה"), ("Esther Rabbah", "אסתר רבה")]),
    ("שאר מדרשים", [("Midrash Tanchuma", "מדרש תנחומא"), ("Pesikta D'Rav Kahanna", "פסיקתא דרב כהנא")]),
]

# Phrases that introduce a popular saying. Each match is labeled so it can be reviewed.
MARKERS = [
    ("אמרי אינשי", r"(?:אמרי|אמרין)\s+(?:אינשי|אינשין|אנשי)|אינשי\s+אמרי"),
    ("מתלא", r"מתלא|מתלי"),
    ("משל הדיוט", r"משל\s+הדיוט"),
    ("בני נשא", r"(?:אמרי|אמרין)\s+בני\s+נשא|בני\s+נשא\s+אמרי"),
    ("הבריות אומרות", r"(?:אומרים|אומרות|אמרו)\s+הבריות|הבריות\s+(?:אומרים|אומרות)"),
]
MARKER_RE = [(name, re.compile(p)) for name, p in MARKERS]
NIKUD = re.compile(r"[\u0591-\u05BD\u05BF-\u05C7]")
FOOTNOTE = re.compile(r'<sup[^>]*class="footnote-marker"[^>]*>.*?</sup>|<i[^>]*class="footnote"[^>]*>.*?</i>', re.S)
TAGS = re.compile(r"<[^>]+>")

def clean(s):
    s = FOOTNOTE.sub("", s or "")
    s = html.unescape(TAGS.sub("", s)).replace("\u05BE", " ")
    return re.sub(r"\s+", " ", NIKUD.sub("", s)).strip()

def get(ref, pad=True):
    q = "?context=0&commentary=0" + ("" if pad else "&pad=0")
    url = API + urllib.parse.quote(ref) + q
    for i in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "amrei-inshi-site/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            if i == 5:
                raise
            time.sleep(2 * (i + 1))

def flatten(x, path=()):
    """Yield (path, string) for nested text lists."""
    if isinstance(x, str):
        yield path, x
    elif isinstance(x, list):
        for i, y in enumerate(x, 1):
            yield from flatten(y, path + (i,))

def excerpt(text, m):
    start = text.rfind(" ", 0, m.start()) + 1
    before = text[:start].split()
    if before and before[-1].strip(".,:") in ("היינו", "והיינו", "הוא", "הדא"):
        start = text.rfind(before[-1], 0, start)
    out = []
    for w in text[start:].split():
        out.append(w)
        if len(out) > 4 and (w.endswith(":") or w.endswith(".") or len(out) >= 28):
            break
    return " ".join(out)

def scan_book(title, he, corpus, group):
    items, ref, seen = [], title, set()
    d = get(ref)
    while d and ref not in seen:
        seen.add(ref)
        sec_ref, he_ref = d.get("ref", ref), d.get("heRef", "")
        en = dict(flatten(d.get("text", [])))
        for path, raw in flatten(d.get("he", [])):
            t = clean(raw)
            if not t:
                continue
            for name, rx in MARKER_RE:
                m = rx.search(t)
                if m:
                    seg = sec_ref + ":" + ":".join(map(str, path)) if path else sec_ref
                    items.append({
                        "ref": seg,
                        "heRef": he_ref,
                        "url": "https://www.sefaria.org/" + urllib.parse.quote(seg.replace(" ", "_")) + "?lang=he",
                        "marker": name,
                        "excerpt": excerpt(t, m),
                        "text": t,
                        "en": clean(en.get(path, ""))[:800],
                    })
                    break
        nxt = d.get("next")
        if not nxt or d.get("indexTitle", title) != title:
            break
        ref = nxt
        time.sleep(0.15)
        d = get(ref, pad=False)
        if d.get("indexTitle", title) != title:
            break
    print(f"{title}: {len(items)} ({len(seen)} sections)", flush=True)
    return {"id": title, "he": he, "corpus": corpus, "group": group, "items": items}

def main():
    old = {}
    if OUT.exists():
        try:
            old = {b["id"]: b for b in json.loads(OUT.read_text("utf-8")).get("books", [])}
        except Exception:
            pass
    jobs = [(t, h, c, g) for c, lst in (("bavli", BAVLI), ("midrash", MIDRASH))
            for g, books in lst for t, h in books]
    books = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(scan_book, *j) for j in jobs]
        for j, f in zip(jobs, futs):
            try:
                books.append(f.result())
            except Exception as e:
                print(f"FAILED {j[0]}: {e}", flush=True)
                if j[0] in old:
                    books.append(old[j[0]])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "source": "Sefaria.org",
        "books": books,
    }, ensure_ascii=False, indent=1), "utf-8")
    print("total:", sum(len(b["items"]) for b in books))

if __name__ == "__main__":
    main()
