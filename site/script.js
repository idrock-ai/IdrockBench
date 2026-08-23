// ============================================================
// eval.idrock.uz — leaderboard
//
// Renders results.json exactly as `idrockbench report` produces it. Three
// contracts this file must not break:
//
//   1. Ranks come from the file. They are computed once from the canonical
//      composite and are never recomputed from whatever column the reader
//      last clicked — sorting a table is not a re-ranking of the models.
//   2. A model without a composite is unranked and shown below the ranked
//      rows. Averaging over whatever subset a model happens to have makes two
//      numbers incomparable while presenting them as a ranking.
//   3. Every cell shows its sample size and interval. Cells flagged
//      provisional or at-or-below-chance say so.
// ============================================================

const CONFIG = { resultsFile: "results.json" };

// Rows visible before the table scrolls. Mirrors --lb-visible-rows in the CSS.
const VISIBLE_ROWS = 10;

const DEFAULT_LANG = "uz";
const SUPPORTED_LANGS = ["uz", "en"];
const LANG_STORAGE_KEY = "idrock-eval-lang";

// Display names per task id. A task present in results.json but missing here
// still renders, using its id — the table follows the data, not this list.
const TASK_LABELS = {
    dtm: { uz: "DTM", en: "DTM" },
    reasoning_uz: { uz: "Mantiqiy fikrlash", en: "Reasoning" },
    translation_uz: { uz: "Tarjima", en: "Translation" },
    ifeval_uz: { uz: "Ko'rsatmalar", en: "Instructions" },
    business_uz: { uz: "Biznes bilimi", en: "Business knowledge" },
};

const TRANSLATIONS = {
    uz: {
        "page.title": "idrock eval — O'zbek tili LLM benchmark",
        "nav.leaderboard": "Reyting",
        "nav.benchmarks": "Benchmarklar",
        "nav.methodology": "Metodologiya",
        "nav.submit": "Model yuborish",
        "nav.about": "Loyiha haqida",
        "hero.subtitle": "O'zbek tili modellari uchun benchmark",
        "hero.description": "Katta til modellarini o'zbek tilida baholash. Har bir natija ishonch oralig'i va tanlanma hajmi bilan chop etiladi.",
        "hero.cta_leaderboard": "Reytingni ko'rish",
        "lb.title": "Reyting",
        "lb.subtitle": "Har bir katakda ishonch oralig'i (95%) va baholangan savollar soni ko'rsatilgan",
        "lb.search": "Modellarni qidirish...",
        "lb.open_source": "Faqat ochiq vaznli",
        "lb.updated": "Yangilangan",
        "lb.suite": "To'plam",
        "lb.empty": "Natijalar yuklanmadi.",
        "lb.nomatch": "Qidiruvga mos model topilmadi.",
        "lb.total": "Jami {total} ta model",
        "lb.unranked": "To'liq baholanmagan modellar",
        "lb.unranked_note": "Bu modellar to'plamdagi barcha topshiriqlarni bajarmagan, shuning uchun ularga umumiy ball berilmaydi.",
        "lb.chance": "Tasodifiy javob darajasi",
        "th.rank": "O'rin",
        "th.model": "Model",
        "th.organization": "Tashkilot",
        "th.overall": "Umumiy",
        "note.composite": "«Umumiy» — har bir topshiriqning tasodifiy javob darajasiga nisbatan normallashtirilgan ballarning o'rtachasi. Faqat barcha topshiriqlarni bajargan modellar uchun ko'rsatiladi.",
        "note.provisional": "◐ — savollarning 20% dan ortig'i baholanmadi.",
        "note.chance": "⚠ — natija tasodifiy javob darajasida yoki undan past.",
        "bench.title": "Benchmarklar",
        "bench.subtitle": "Baholanadigan yo'nalishlar",
        "about.title": "Loyiha haqida",
        "about.subtitle": "eval.idrock.uz — Yangi O'zbekiston Universiteti qoshidagi sun'iy intellekt laboratoriyasi idrock tomonidan ishlab chiqilgan",
        "about.idrock.desc": "Markaziy Osiyoda ilg'or sun'iy intellekt yechimlarini yaratish va AI tadqiqotlarini rivojlantirishga yo'naltirilgan AI laboratoriyasi.",
        "about.newuu.name": "Yangi O'zbekiston Universiteti",
        "about.newuu.desc": "Jahon darajasidagi tadqiqotlar, innovatsiyalar va O'zbekistondagi yangi avlod texnologiya iqtidorlarini tayyorlashga sodiq bo'lgan yetakchi oliy ta'lim muassasasi.",
        "footer.contact": "Bog'lanish",
        "submit.title": "Modelni baholashga yuborish",
        "submit.subtitle": "Modelingizni idrock eval benchmarki bo'yicha baholashga taklif qiling.",
        "submit.field.name": "Ismingiz",
        "submit.field.name_ph": "Alisher Karimov",
        "submit.field.email": "Email",
        "submit.field.model": "Model nomi",
        "submit.field.company": "Kompaniya",
        "submit.field.notes": "Qo'shimcha izoh",
        "submit.field.notes_ph": "Model haqida qo'shimcha ma'lumot, inference sozlamalari, va h.k.",
        "submit.field.consent": "Ariza ko'rib chiqilishi uchun ismim va email manzilim saqlanishiga roziman.",
        "submit.cta": "Yuborish",
        "submit.note": "* bilan belgilangan maydonlar majburiy. Iltimos, maxfiy API kalitlarini bu yerda yubormang.",
        "submit.status.sending": "Yuborilmoqda...",
        "submit.status.success": "Rahmat! Arizangiz qabul qilindi.",
        "submit.status.error": "Yuborishda xatolik yuz berdi. Iltimos, idrock@newuu.uz ga yozing.",
        "submit.status.required": "Iltimos, barcha majburiy (*) maydonlarni to'ldiring.",
    },
    en: {
        "page.title": "idrock eval — Uzbek LLM Benchmark",
        "nav.leaderboard": "Leaderboard",
        "nav.benchmarks": "Benchmarks",
        "nav.methodology": "Methodology",
        "nav.submit": "Submit a Model",
        "nav.about": "About",
        "hero.subtitle": "A benchmark for Uzbek-language models",
        "hero.description": "Evaluating large language models on Uzbek. Every result is published with its confidence interval and sample size.",
        "hero.cta_leaderboard": "View Leaderboard",
        "lb.title": "Leaderboard",
        "lb.subtitle": "Every cell shows a 95% confidence interval and the number of items scored",
        "lb.search": "Search models...",
        "lb.open_source": "Open weights only",
        "lb.updated": "Updated",
        "lb.suite": "Suite",
        "lb.empty": "Results could not be loaded.",
        "lb.nomatch": "No model matches that search.",
        "lb.total": "{total} models",
        "lb.unranked": "Models without a complete run",
        "lb.unranked_note": "These models did not complete every task in the suite, so no composite score is shown.",
        "lb.chance": "Random baseline",
        "th.rank": "Rank",
        "th.model": "Model",
        "th.organization": "Organization",
        "th.overall": "Overall",
        "note.composite": "\"Overall\" is the mean of per-task scores normalised against each task's random baseline. Shown only for models with a complete run.",
        "note.provisional": "◐ — more than 20% of items could not be scored.",
        "note.chance": "⚠ — score is at or below the random baseline.",
        "bench.title": "Benchmarks",
        "bench.subtitle": "Evaluated tracks",
        "about.title": "About",
        "about.subtitle": "eval.idrock.uz is built by idrock, the AI lab at New Uzbekistan University",
        "about.idrock.desc": "An AI lab focused on building advanced AI solutions and advancing artificial intelligence research in Central Asia.",
        "about.newuu.name": "New Uzbekistan University",
        "about.newuu.desc": "A leading institution of higher education committed to world-class research, innovation, and developing the next generation of tech talent in Uzbekistan.",
        "footer.contact": "Contact",
        "submit.title": "Submit a Model for Evaluation",
        "submit.subtitle": "Propose your model to be evaluated on the idrock eval benchmark.",
        "submit.field.name": "Your name",
        "submit.field.name_ph": "Jane Doe",
        "submit.field.email": "Email",
        "submit.field.model": "Model name",
        "submit.field.company": "Company",
        "submit.field.notes": "Additional notes",
        "submit.field.notes_ph": "Anything else about the model, inference settings, etc.",
        "submit.field.consent": "I agree that my name and email may be stored so this submission can be reviewed.",
        "submit.cta": "Submit",
        "submit.note": "Fields marked * are required. Please don't send secret API keys here.",
        "submit.status.sending": "Sending...",
        "submit.status.success": "Thank you! Your submission was received.",
        "submit.status.error": "Something went wrong. Please email idrock@newuu.uz.",
        "submit.status.required": "Please fill in all required (*) fields.",
    },
};

let currentLang = DEFAULT_LANG;
let BOARD = { models: [], tasks: [] };

const state = { sortBy: "rank", sortDir: "asc", searchQuery: "", openWeightsOnly: false };

const dom = {
    body: document.getElementById("leaderboardBody"),
    head: document.getElementById("leaderboardHead"),
    search: document.getElementById("searchInput"),
    openWeights: document.getElementById("openWeightsToggle"),
    meta: document.getElementById("leaderboardMeta"),
    table: document.getElementById("leaderboardTable"),
    langToggle: document.getElementById("langToggle"),
    hamburger: document.getElementById("hamburger"),
    navLinks: document.getElementById("navLinks"),
};

// -- i18n -----------------------------------------------------------------

function t(key) {
    return (TRANSLATIONS[currentLang] || TRANSLATIONS.uz)[key] ?? key;
}

function applyLanguage(lang) {
    currentLang = SUPPORTED_LANGS.includes(lang) ? lang : DEFAULT_LANG;
    const dict = TRANSLATIONS[currentLang];
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        if (dict[el.dataset.i18n] != null) el.textContent = dict[el.dataset.i18n];
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
        if (dict[el.dataset.i18nPlaceholder] != null) {
            el.setAttribute("placeholder", dict[el.dataset.i18nPlaceholder]);
        }
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
        if (dict[el.dataset.i18nAria] != null) {
            el.setAttribute("aria-label", dict[el.dataset.i18nAria]);
        }
    });
    if (dict["page.title"]) document.title = dict["page.title"];
    document.documentElement.lang = currentLang;
    document.querySelectorAll(".lang-btn").forEach((b) => {
        const on = b.dataset.lang === currentLang;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", String(on));
    });
    try { localStorage.setItem(LANG_STORAGE_KEY, currentLang); } catch { /* private mode */ }
    render();
}

// -- rendering ------------------------------------------------------------

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function taskLabel(id) {
    return TASK_LABELS[id]?.[currentLang] ?? id;
}

function renderHead() {
    const cols = BOARD.tasks
        .map((task) => {
            const chance = task.chance > 0
                ? `<span class="th-chance">${t("lb.chance")}: ${task.chance}%</span>` : "";
            return `<th class="col-score" scope="col">
                        <button type="button" class="th-sort" data-sort="${esc(task.id)}">
                            ${esc(taskLabel(task.id))}<span class="sort-icon" aria-hidden="true"></span>
                        </button>${chance}
                    </th>`;
        })
        .join("");
    dom.head.innerHTML = `<tr>
        <th class="col-rank" scope="col"><span data-i18n="th.rank">${t("th.rank")}</span></th>
        <th class="col-model" scope="col"><span data-i18n="th.model">${t("th.model")}</span></th>
        <th class="col-org" scope="col"><span data-i18n="th.organization">${t("th.organization")}</span></th>
        <th class="col-score" scope="col">
            <button type="button" class="th-sort" data-sort="composite">
                ${t("th.overall")}<span class="sort-icon" aria-hidden="true"></span>
            </button>
        </th>
        ${cols}
    </tr>`;
}

// Tint a score by how far it sits above the task's random baseline, not by its
// raw value: 25% is a coin flip on a four-option task and real signal on a
// ten-option one, so a raw-value ramp would colour them the same.
function scoreTint(entry) {
    const chance = (entry.chance ?? 0) / 100;
    const raw = (entry.score ?? 0) / 100;
    const headroom = 1 - chance;
    const ratio = headroom > 0 ? Math.max(0, Math.min(1, (raw - chance) / headroom)) : raw;
    const hue = 8 + ratio * 132;                    // red -> green
    // Lightness floors at 62% so the weakest cell still clears AA on the dark
    // ground; the old ramp bottomed out at 4.37:1.
    return {
        bg: `hsla(${hue}, 58%, 42%, 0.16)`,
        fg: `hsl(${hue}, 62%, ${62 + ratio * 10}%)`,
    };
}

function cell(entry) {
    if (!entry || entry.score == null) {
        return `<td class="col-score"><span class="score-missing" title="not run">—</span></td>`;
    }
    const flags = [];
    if (entry.at_or_below_chance) flags.push(`<span class="flag flag-chance" title="${esc(t("note.chance"))}">⚠</span>`);
    if (entry.provisional) flags.push(`<span class="flag flag-provisional" title="${esc(t("note.provisional"))}">◐</span>`);
    const ci = entry.ci_low != null && entry.ci_high != null
        ? `<span class="score-ci">${entry.ci_low.toFixed(1)}–${entry.ci_high.toFixed(1)}</span>` : "";
    const n = entry.n != null ? `<span class="score-n">n=${entry.n}</span>` : "";
    const tint = scoreTint(entry);
    return `<td class="col-score">
        <span class="score-value" style="background:${tint.bg};color:${tint.fg}">${entry.score.toFixed(1)}${flags.join("")}</span>
        ${ci}${n}
    </td>`;
}

function reasoningBadge(reasoning) {
    if (!reasoning || !reasoning.label || reasoning.label === "unknown") return "";
    const perTask = Object.entries(reasoning.byTask || {})
        .map(([task, mode]) => `${task}: ${mode}`).join(" · ");
    const text = { "no-think": "no-think", think: "think", mixed: "think: mixed" }[reasoning.label];
    return `<span class="badge badge-think badge-think-${esc(reasoning.label)}" `
         + `title="${esc(perTask)}">${esc(text)}</span>`;
}

// Size the scroll region to exactly VISIBLE_ROWS rows, measured after render.
// Row height is not knowable in CSS: it changes with badges, wrapping and the
// number of score columns in the suite.
function sizeScrollRegion(totalModels) {
    const container = dom.table?.closest(".table-container");
    if (!container) return;
    const rows = dom.body.querySelectorAll("tr");
    const head = dom.head?.getBoundingClientRect().height || 0;

    if (rows.length > VISIBLE_ROWS) {
        let h = head;
        for (let i = 0; i < VISIBLE_ROWS; i++) h += rows[i].getBoundingClientRect().height;
        container.style.setProperty("--lb-max-height", `${Math.ceil(h)}px`);
        container.classList.add("is-scrollable");
    } else {
        container.style.removeProperty("--lb-max-height");
        container.classList.remove("is-scrollable");
    }

    const countEl = document.getElementById("leaderboardCount");
    if (countEl) {
        countEl.textContent = totalModels
            ? t("lb.total").replace("{total}", totalModels)
            : "";
    }
}

function metaLine(model) {
    const bits = [model.runDate, model.harnessCommit].filter(
        (b) => b && b !== "unknown");
    return bits.length ? `<span class="model-meta">${esc(bits.join(" · "))}</span>` : "";
}

function row(model) {
    const badge = model.openWeights
        ? `<span class="badge badge-open" title="${esc(model.license)}">open</span>` : "";
    const quant = model.quantization
        ? `<span class="badge badge-quant" title="quantisation">${esc(model.quantization)}</span>` : "";
    // Whether the model reasoned before answering changes what the score
    // measures, so it is shown on the row, not hidden in the raw JSON.
    const think = reasoningBadge(model.reasoning);
    // Rank comes from the file. Sorting a column never reassigns it.
    const rank = model.rank == null
        ? `<span class="rank-cell rank-unranked">—</span>`
        : `<span class="rank-cell">${model.rank}</span>`;
    const tied = model.tiedWith?.length
        ? `<span class="tie-note" title="${esc(model.tiedWith.join(", "))}">tied</span>` : "";
    const composite = model.composite == null
        ? `<td class="col-score"><span class="score-missing" title="${esc(t("lb.unranked_note"))}">—</span></td>`
        : `<td class="col-score"><span class="score-value score-composite">${model.composite.toFixed(1)}</span></td>`;
    void 0;

    return `<tr${model.composite == null ? ' class="row-unranked"' : ""}>
        <td class="col-rank">${rank}${tied}</td>
        <th class="col-model" scope="row">
            <span class="model-name">${esc(model.model)}</span>${badge}${quant}${think}
            ${metaLine(model)}
        </th>
        <td class="col-org">${esc(model.organization)}</td>
        ${composite}
        ${BOARD.tasks.map((task) => cell(model.scores?.[task.id])).join("")}
    </tr>`;
}

function visibleModels() {
    let data = [...BOARD.models];
    if (state.searchQuery) {
        const q = state.searchQuery.toLowerCase();
        data = data.filter((d) =>
            d.model.toLowerCase().includes(q) || d.organization.toLowerCase().includes(q));
    }
    if (state.openWeightsOnly) data = data.filter((d) => d.openWeights);

    const key = state.sortBy;
    data.sort((a, b) => {
        if (key === "rank") {
            // Unranked rows always sink, in both directions: they are not
            // "worse", they are not comparable.
            if (a.rank == null && b.rank == null) return a.model.localeCompare(b.model);
            if (a.rank == null) return 1;
            if (b.rank == null) return -1;
            return a.rank - b.rank;
        }
        const va = key === "composite" ? a.composite : a.scores?.[key]?.score;
        const vb = key === "composite" ? b.composite : b.scores?.[key]?.score;
        if (va == null && vb == null) return 0;
        if (va == null) return 1;      // missing sinks in both directions
        if (vb == null) return -1;
        return state.sortDir === "asc" ? va - vb : vb - va;
    });
    return data;
}

function render() {
    if (!dom.body) return;
    renderHead();

    const models = visibleModels();
    if (!models.length) {
        const cols = 4 + BOARD.tasks.length;
        // Distinguish "nothing has been benchmarked" from "the fetch failed" —
        // a silently blank table reads the same as a broken site.
        const msg = BOARD.notes?.status
            ? esc(BOARD.notes.status)
            : (BOARD.models?.length ? esc(t("lb.nomatch")) : esc(t("lb.empty")));
        dom.body.innerHTML = `<tr><td colspan="${cols}" class="table-empty">${msg}</td></tr>`;
    } else {
        dom.body.innerHTML = models.map(row).join("");
    }

    sizeScrollRegion(models.length);

    if (dom.meta) {
        const generated = (BOARD.generatedAt || "").slice(0, 10);
        const versions = BOARD.tasks.map((x) => `${taskLabel(x.id)} v${x.version}`).join(" · ");
        dom.meta.innerHTML = `
            <span>${esc(t("lb.updated"))}: <strong>${esc(generated || "—")}</strong></span>
            <span>${esc(t("lb.suite"))}: <strong>${esc(BOARD.suite || "—")}</strong></span>
            <span class="meta-versions">${esc(versions)}</span>`;
    }

    document.querySelectorAll(".th-sort").forEach((btn) => {
        const active = btn.dataset.sort === state.sortBy;
        btn.closest("th").setAttribute("aria-sort",
            active ? (state.sortDir === "asc" ? "ascending" : "descending") : "none");
        btn.classList.toggle("is-active", active);
    });
}

// -- events ---------------------------------------------------------------

dom.table?.querySelector("thead")?.addEventListener("click", (e) => {
    const btn = e.target.closest(".th-sort");
    if (!btn) return;
    const key = btn.dataset.sort;
    if (state.sortBy === key) {
        state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
    } else {
        state.sortBy = key;
        state.sortDir = "desc";
    }
    render();
});

let searchTimer;
dom.search?.addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const value = e.target.value.trim();
    searchTimer = setTimeout(() => { state.searchQuery = value; render(); }, 150);
});

dom.openWeights?.addEventListener("change", (e) => {
    state.openWeightsOnly = e.target.checked;
    render();
});

dom.langToggle?.addEventListener("click", (e) => {
    const btn = e.target.closest(".lang-btn");
    if (btn && btn.dataset.lang !== currentLang) applyLanguage(btn.dataset.lang);
});

dom.hamburger?.addEventListener("click", () => {
    const open = dom.navLinks.classList.toggle("open");
    dom.hamburger.classList.toggle("active", open);
    dom.hamburger.setAttribute("aria-expanded", String(open));
});

dom.navLinks?.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
        dom.navLinks.classList.remove("open");
        dom.hamburger?.classList.remove("active");
        dom.hamburger?.setAttribute("aria-expanded", "false");
    });
});

// -- load -----------------------------------------------------------------

async function load() {
    try {
        const res = await fetch(CONFIG.resultsFile, { cache: "no-cache" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        BOARD = {
            suite: data.suite,
            generatedAt: data.generatedAt,
            tasks: data.tasks || [],
            models: data.models || [],
            notes: data.notes || {},
        };
    } catch (err) {
        // Fail visibly. A silently empty leaderboard is indistinguishable from
        // a benchmark nobody has run.
        console.error("Could not load results:", err);
        BOARD = { models: [], tasks: [] };
        if (dom.meta) dom.meta.innerHTML = `<span class="meta-error">${esc(t("lb.empty"))}</span>`;
    }
    render();
}

function initialLang() {
    try {
        const saved = localStorage.getItem(LANG_STORAGE_KEY);
        if (saved && SUPPORTED_LANGS.includes(saved)) return saved;
    } catch { /* private mode */ }
    const url = new URLSearchParams(location.search).get("lang");
    return SUPPORTED_LANGS.includes(url) ? url : DEFAULT_LANG;
}

let resizeTimer;
window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => sizeScrollRegion(visibleModels().length), 150);
});

applyLanguage(initialLang());
load();
