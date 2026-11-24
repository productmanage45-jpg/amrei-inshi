(() => {
  const MARK = /(?:אמרי|אמרין)\s+(?:אינשי|אינשין|אנשי|אינישי)|אמרו\s+(?:אינשי|אינשין)|אינשי\s+אמרי|מתלא|מתלי|משל\s+(?:ה)?הדיוט|הדיוט\s+(?:אומר|אמר)|(?:אמרי|אמרין)\s+בני\s+נשא|בני\s+נשא\s+אמרי|(?:אומרים|אומרות|אמרו|אמרי)\s+(?:ה)?בריות|הבריות\s+(?:אומרים|אומרות)/g;
  const T = {
    yi: { dir: "rtl", tagline: "יעדעס מאָל וואָס די גמרא ברענגט אַ ווערטל וואָס מענטשן זאָגן — לויט מסכתא, מיט אַ לינק צום מקור.",
      search: "זוך אַ ווערטל…", all: "גאַנץ ש״ס", allBavli: "גאַנץ ש״ס", flag: "נאָר אין ווילנער ש״ס",
      searching: "זוכן: ", count: n => `${n} ווערטלעך`, show: "ווייז די גאַנצע שורה", hide: "באַהאַלט",
      none: "קיין ווערטל טרעפט נישט — פרובירט אַן אַנדער וואָרט.", building: "די זאַמלונג ווערט נאָך צוגעגרייט.",
      failed: "די דאַטן האָבן נישט געלאָדן.", credit: "טעקסט פון", updated: d => `דערהיינטיקט ${d}.` },
    en: { dir: "ltr", tagline: "Every time the Gemara quotes a saying “that people say” — by masechta, with a link to the source.",
      search: "Search a saying…", all: "All of Shas", allBavli: "All of Shas", flag: "Only in the Vilna edition",
      searching: "Search: ", count: n => `${n} ${n === 1 ? "saying" : "sayings"}`, show: "Show full passage", hide: "Hide",
      none: "No sayings match — try another word.", building: "The collection is still being built.",
      failed: "The data didn’t load.", credit: "Text from", updated: d => `Updated ${d}.` },
  };
  const GROUP_EN = { "סדר זרעים": "Seder Zeraim", "סדר מועד": "Seder Moed", "סדר נשים": "Seder Nashim", "סדר נזיקין": "Seder Nezikin",
    "סדר קדשים": "Seder Kodashim", "סדר טהרות": "Seder Taharos" };

  const $ = s => document.querySelector(s);
  const saved = (() => { try { return localStorage.getItem("lang"); } catch { return null; } })();
  const state = { book: null, q: "", lang: saved === "en" ? "en" : "yi" };
  let DATA = { books: [] };
  const t = () => T[state.lang];
  const en = () => state.lang === "en";

  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const strip = s => s.replace(/[\u0591-\u05C7]/g, "");
  const highlight = s => esc(s).replace(MARK, m => `<mark>${m}</mark>`);
  const books = () => DATA.books.filter(b => b.corpus === "bavli");
  const bookName = b => en() ? b.id : b.he;
  const groupName = g => en() ? (GROUP_EN[g] || g) : g;
  const srcName = it => en() ? it.ref.replace(/:\d+(?::\d+)*$/, "") : (it.heRef || it.ref);

  function applyLang() {
    const L = t();
    document.documentElement.lang = state.lang; document.documentElement.dir = L.dir;
    $("#tagline").textContent = L.tagline;
    document.querySelectorAll(".langs button").forEach(b => b.setAttribute("aria-pressed", b.dataset.lang === state.lang));
    $("#q").placeholder = L.search; $("#q").setAttribute("aria-label", L.search);
    $("#credit").textContent = L.credit;
    $("#updated").textContent = DATA.generated ? L.updated(DATA.generated) : "";
  }

  function renderShelf() {
    const nav = $("#shelf"), sel = $("#shelfSelect");
    nav.innerHTML = ""; sel.innerHTML = "";
    let group = null, og = null;
    const total = books().reduce((n, b) => n + b.items.length, 0);
    const all = document.createElement("button");
    all.innerHTML = `<span>${t().all}</span><span class="n">${total}</span>`;
    all.onclick = () => go(null);
    all.setAttribute("aria-current", state.book === null);
    nav.append(all);
    sel.append(new Option(`${t().all} (${total})`, ""));
    for (const b of books()) {
      if (b.group !== group) {
        group = b.group;
        const h = document.createElement("h3"); h.textContent = groupName(group); nav.append(h);
        og = document.createElement("optgroup"); og.label = groupName(group); sel.append(og);
      }
      const btn = document.createElement("button");
      btn.innerHTML = `<span>${esc(bookName(b))}</span><span class="n">${b.items.length}</span>`;
      if (!b.items.length) btn.classList.add("zero");
      btn.setAttribute("aria-current", state.book === b.id);
      btn.onclick = () => go(b.id);
      nav.append(btn);
      og.append(new Option(`${bookName(b)} (${b.items.length})`, b.id));
    }
    sel.value = state.book || "";
  }

  function renderList() {
    const L = t(), list = $("#list"), empty = $("#empty");
    const raw = state.q.trim(), q = strip(raw), ql = q.toLowerCase();
    let pool = books();
    if (state.book && !q) pool = pool.filter(b => b.id === state.book);
    const rows = [];
    for (const b of pool) for (const it of b.items) {
      if (q && !(it.text.includes(q) || it.heRef.includes(q) || it.ref.toLowerCase().includes(ql) || b.he.includes(q) || (it.en || "").toLowerCase().includes(ql))) continue;
      rows.push([b, it]);
    }
    const cur = DATA.books.find(b => b.id === state.book);
    $("#bookTitle").textContent = q ? L.searching + raw : (cur ? bookName(cur) : L.allBavli);
    $("#bookCount").textContent = L.count(rows.length);
    list.innerHTML = rows.map(([b, it], i) => `
      <li>
        <p class="saying" lang="he">${highlight(it.excerpt)}</p>
        <div class="meta">
          <a class="src" href="${esc(it.url.replace("?lang=he", en() ? "?lang=bi" : "?lang=he"))}" target="_blank" rel="noopener">${esc(srcName(it))}</a>
          ${state.book && !q ? "" : `<span class="book">${esc(bookName(b))}</span>`}
          ${it.flag === "only-in-vilna" ? `<span class="flag">${L.flag}</span>` : ""}
          <button data-i="${i}" aria-expanded="false">${L.show}</button>
        </div>
      </li>`).join("");
    list.querySelectorAll("button[data-i]").forEach(btn => btn.onclick = () => {
      const li = btn.closest("li"), open = li.querySelector(".full");
      if (open) { open.remove(); btn.textContent = t().show; btn.setAttribute("aria-expanded", "false"); return; }
      const it = rows[+btn.dataset.i][1], div = document.createElement("div");
      div.className = "full";
      div.innerHTML = `<p class="rashi" lang="he">${highlight(it.text)}</p>${it.en ? `<p class="en">${esc(it.en)}</p>` : ""}`;
      li.append(div); btn.textContent = t().hide; btn.setAttribute("aria-expanded", "true");
    });
    empty.hidden = rows.length > 0;
    empty.textContent = DATA.books.length ? L.none : L.building;
  }

  function go(id) {
    state.book = id;
    history.replaceState(null, "", id ? "#" + encodeURIComponent(id) : location.pathname);
    renderShelf(); renderList(); window.scrollTo({ top: 0 });
  }
  function setLang(l) {
    state.lang = l;
    try { localStorage.setItem("lang", l); } catch {}
    applyLang(); renderShelf(); renderList();
  }

  document.querySelectorAll(".langs button").forEach(b => b.onclick = () => setLang(b.dataset.lang));
  $("#shelfSelect").onchange = e => go(e.target.value || null);
  let timer; $("#q").oninput = e => { clearTimeout(timer); timer = setTimeout(() => { state.q = e.target.value; renderList(); }, 150); };

  applyLang();
  fetch("data/sayings.json", { cache: "no-cache" }).then(r => r.json()).then(d => {
    DATA = d;
    const h = decodeURIComponent(location.hash.slice(1));
    const b = d.books.find(x => x.id === h);
    if (b) state.book = b.id;
    applyLang(); renderShelf(); renderList();
  }).catch(() => { $("#empty").hidden = false; $("#empty").textContent = t().failed; });
})();
