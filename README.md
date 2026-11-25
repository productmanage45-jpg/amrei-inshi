# אמרי אינשי

Every place in Talmud Bavli (by masechta) where a popular saying is quoted
("אמרי אינשי", "היינו דאמרי אינשי", "מתלא", "משל הדיוט" …), each with a clickable Sefaria source and an English translation (William Davidson Edition, via Sefaria).

## How the list is checked
1. **Full scan** of Shas (Sefaria, William Davidson Aramaic). Every match in a line is kept, not just the first.
2. **Second edition**: every amud is rescanned in the Vilna text from Wikisource. Anything only that edition has is added and flagged.
3. **Source check**: every source is fetched again on its own to confirm the saying is there. Lines with אינשי / מתלא / הדיוט / בריות that no marker caught are listed in `data/review.json` for a person to look at.

## Setup (GitHub Pages)
1. Settings → Pages → Deploy from branch → `main` / root.
2. Actions → "Build sayings data" → Run workflow. It commits `data/sayings.json` and `data/review.json`, and re-runs monthly.

## Adding phrases
Edit `MARKERS` in `scripts/build_data.py` (and the `MARK` regex in `app.js` for highlighting), then re-run the workflow.
