// EN / 日本語. Static text: [data-i18n] keys. Dynamic text: t(key, vars) called by app.js.
const DICT = {
  en: {},
  ja: {
    eyebrow: "daytona hacksprint · 東京",
    tag: "たくさん作り、全部走らせ、<b>証明されたものだけ残す。</b>",
    sub: "地図タイルライブラリの1文字のバグで、衛星画像パイプラインが地球の反対側を取りに行く。東京の画像を頼むと、返ってくるのは南極の氷。Everett は <b>Daytona 上に 32 の並行世界</b>を立ち上げ、<b>Nosana</b> 上のオープンなコーディングモデルが世界ごとに違う修正を試す。各世界が実際に取得した衛星画像を見せ、テストが本物の世界を決め、残り 31 は捨てる。",
    cta_real: "実際の実行を見る", cta_demo: "台本どおりのデモ", cta_live: "ライブに接続",
    m_created: "生成した世界", m_disposed: "破棄", m_merged: "マージ", m_boxes: "稼働中のサンドボックス",
    m_fork: "世界の起動 p50", m_time: "経過時間", m_tokens: "Nosana トークン",
    branches: "ブランチ", qr: "スマホで一緒に見る", pause: "一時停止", play: "再生", restart: "最初から",
    pr_bad: "壊れたパイプライン", pr_good: "正解の位置",
    pr_arrow: "CI が赤 — パイプラインは<span>{label}</span>がここにあると思っている。本当はあそこ。",
    tests_green: "テスト合格", worlds_tried: "試した世界", wall_time: "所要時間", back: "壁に戻る",
    ph_wait: "壊れたビルドを待っています…", ph_base: "ベースの世界を構築中…",
    ph_red: "<b>CI が赤:</b> {n} 件失敗 / 全 {total} 件 · {err}",
    ph_hyp: "<b>Nosana</b> が仮説を {n} 個提案 — パッチを生成中",
    ph_r1: "<b>1周目:</b> {n} の世界が、それぞれ違う修正を試しています",
    ph_r2: "<b>{r}周目:</b> いちばん惜しかった世界から、もう一度分岐",
    ph_proven: "<b>証明:</b> {id} — 他の世界はすべて破棄",
    ph_none: "<b>合格した世界はありませんでした</b>",
    ph_done: "<b>完了。</b>試した世界 {c} · 破棄 {d} · マージ {m}",
    ph_failed: "<b>実行失敗</b> {stage}: {msg}",
    touches_tests: "テストを改変 — 失格", skip_injection: "テストをスキップ — 失格", no_match: "パッチが当たらない",
    parse_error: "読めないパッチ", empty: "空のパッチ", collect_shrank: "テスト数が減った — 失格",
    starting: "$ 世界を起動中…", polar: "極地の氷", fix_it: "直して — 32 の世界を起動", waiting_run: "管制塔オンライン · 実行待ち",
  },
};
const EN = {
  eyebrow: "daytona hacksprint · tokyo",
  tag: "Generate many. Run all. <b>Keep what's proven.</b>",
  pr_arrow: "CI is red — the pipeline thinks <span>{label}</span> is here. It should be there.",
  ph_wait: "waiting for the broken build…", ph_base: "building the base world…",
  ph_red: "<b>CI is red:</b> {n} failing of {total} · {err}",
  ph_hyp: "<b>Nosana</b> proposed {n} hypotheses — writing patches",
  ph_r1: "<b>round 1:</b> {n} worlds, each trying a different fix",
  ph_r2: "<b>round {r}:</b> branching again from the closest worlds",
  ph_proven: "<b>proven:</b> {id} — throwing away every other world",
  ph_none: "<b>no world passed</b>",
  ph_done: "<b>done.</b> {c} worlds tried · {d} thrown away · {m} merged",
  ph_failed: "<b>run failed</b> at {stage}: {msg}",
  touches_tests: "edited tests — disqualified", skip_injection: "skipped tests — disqualified", no_match: "patch did not apply",
  parse_error: "unreadable patch", empty: "empty patch", collect_shrank: "fewer tests collected — disqualified",
  starting: "$ starting world…", polar: "polar ice", fix_it: "Fix it — launch 32 worlds", waiting_run: "tower online · waiting for a run",
  pause: "Pause", play: "Play",
};
DICT.en = EN;

let lang = "en";
try { lang = new URLSearchParams(location.search).get("lang") || localStorage.getItem("everett-lang") || ""; } catch { lang = ""; }
if (!lang) lang = (navigator.language || "").toLowerCase().startsWith("ja") ? "ja" : "en";

export function getLang() { return lang; }

export function t(key, vars = {}) {
  const s = (DICT[lang] && DICT[lang][key]) ?? EN[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
}

const originals = new WeakMap();
export function applyStatic() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if (!originals.has(el)) originals.set(el, el.innerHTML);
    const key = el.getAttribute("data-i18n");
    const ja = DICT.ja[key];
    el.innerHTML = lang === "ja" && ja ? ja : (EN[key] && el.dataset.i18nEnFromDict !== undefined ? EN[key] : originals.get(el));
  });
  const b = document.getElementById("lang-btn");
  if (b) b.innerHTML = lang === "ja" ? "<b>日本語</b> / EN" : "<b>EN</b> / 日本語";
}

export function onToggle(cb) {
  const b = document.getElementById("lang-btn");
  if (!b) return;
  b.addEventListener("click", () => {
    lang = lang === "ja" ? "en" : "ja";
    try { localStorage.setItem("everett-lang", lang); } catch {}
    applyStatic(); cb && cb();
  });
}
