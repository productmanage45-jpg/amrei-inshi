# אמרי אינשי

Every place in Talmud Bavli (by masechta) and Midrash where a popular saying is quoted
("אמרי אינשי", "היינו דאמרי אינשי", "מתלא", "משל הדיוט" …), each with a clickable Sefaria source.

## Setup (GitHub Pages)
1. Upload all files to a GitHub repo (keep the `.github` folder).
2. Settings → Pages → Deploy from branch → `main` / root.
3. Actions → "Build sayings data" → Run workflow. It reads all of Shas and the Midrashim from
   Sefaria (~15–30 min) and commits `data/sayings.json`. It also re-runs monthly.

## Adding phrases
Edit `MARKERS` in `scripts/build_data.py` (and the `MARK` regex in `app.js` for highlighting), then re-run the workflow.
