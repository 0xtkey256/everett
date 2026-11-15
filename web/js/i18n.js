// EN / 日本語. Static text: [data-i18n] keys. Dynamic text: t(key, vars) called by app.js.
const DICT = {
  en: {},
  ja: {
    eyebrow: "daytona hacksprint · 東京",
    tag: "CI が赤？ 32 通りの修正を同時に試す。<b>テストが証明したものだけ残す。</b>",
    sub: "テストが失敗すると、Everett は <b>32 の並行世界</b>（<b>Daytona</b> の隔離サンドボックス）を開き、私たちの <b>Nosana</b> GPU 上のオープンな AI モデルが世界ごとに違う修正を書きます。すべての世界でテストを全部走らせ、全部に合格した修正だけを残します。",
    how1t: "CI が赤になる", how1: "変更のあとでテストが失敗。ふつうは誰かが手を止め、ログを読んで推測します。",
    how2t: "32 の世界、32 の修正", how2: "それぞれの世界は Daytona の隔離サンドボックス。コードのコピーと、AI が書いた修正を1つずつ持ちます。",
    how3t: "テストが決める", how3: "すべてのテストに合格し、他を何も壊さない修正だけをマージ。残りの 31 は捨てます。",
    example: "今日の例は私たちの世界、衛星画像から。1行の間違いで、地図タイルのライブラリが東京を南極に送ってしまう。各世界は、その修正で取得される衛星画像を表示します。",
    u_daytona: "各世界は、作成済みスナップショット（Python・リポジトリ・依存関係）から起動する Daytona の隔離サンドボックスで動きます。ベース1 + サンドボックス8 × 世界4 = 32 の世界を、10 vCPU のアカウント内で実行。世界の起動は約2秒、テスト全体は2秒未満。サンドボックスにはラベルを付け、実行後にすべて削除します。<code>sandbox.fork()</code>（準備済みの世界をコピーオンライトで複製）を前提に設計。",
    u_nosana: "AI は、Nosana の分散型 GPU ネットワークから借りた NVIDIA RTX 3090（24 GB）1枚で動きます。Nosana のジョブはコンテナの定義（JSON）で、vLLM 0.8.5 が Qwen2.5-Coder-7B-Instruct を OpenAI 互換の HTTPS エンドポイントとして提供し、/v1/models でヘルスチェック。1回のリクエストで違うパッチを8本（n=8）約2.3秒で生成 — vLLM が共通のプロンプトを1回だけ計算し、8通りを並列にサンプリングします。$0.19/時：1回の実行は約3.5万トークン ≈ $0.003。",
    w_single: "AI 1回の試行で直る確率", w_many: "32 の世界なら 7 回中 6 回で修正", w_time: "1回の実行あたり（開始〜終了）",
    w_runs: "実際の実行（全 228 世界）:",
    see_daytona: "Daytona で動いている様子", see_nosana: "Nosana で動いている様子",
    cap_daytona: "実行中の Daytona ダッシュボード：スナップショット <code>everett-base-merc</code> から起動した 9 つのサンドボックス（ベース1 + 世界用8、各 1 vCPU）。",
    cap_nosana: "イベント中の Nosana デプロイ：NVIDIA GeForce RTX 3090 上で <code>coder</code> エンドポイント（:9000）が稼働（エンドポイント URL と ID はぼかし）。",
    b_red_k: "CI が赤", b_red_m: "{n} 件のテストが失敗", b_launch_m: "{n} の世界を起動",
    b_merge_k: "テストで証明", b_merge_m: "1 つをマージ · {d} を破棄", b_none_k: "合格した世界なし", b_none_m: "{c} を試行 · すべて破棄",
    dl_patch: "パッチをダウンロード", copy_pr: "PR の説明文をコピー", copied: "コピーしました",
    step1: "CI が赤", step2: "AI が 32 の修正を書く", step3: "32 の世界でテスト", step4: "証明された修正をマージ",
    legend: "タイル1枚 = 1つの世界：修正1つ + テスト全部 · ✓ 全部合格 · ✗ まだ失敗 · ⊘ 失格・適用できず",
    m_fork: "世界の起動（中央値）", m_tokens: "AI トークン · Nosana",
    cta_real: "実際の実行を見る", cta_demo: "台本どおりのデモ", cta_live: "ライブに接続",
    m_created: "生成した世界", m_disposed: "破棄", m_merged: "マージ", m_boxes: "稼働中のサンドボックス",
    m_time: "経過時間",
    branches: "ブランチ", qr: "スマホで一緒に見る", pause: "一時停止", play: "再生", restart: "最初から",
    pr_bad: "壊れたパイプライン", pr_good: "正解の位置",
    pr_arrow: "バグ：<span>{label}</span> を頼むと、左の画像が返ってくる。正しくは右。",
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
  tag: "CI is red? Try 32 fixes at once. <b>Keep only what the tests prove.</b>",
  pr_arrow: "The bug: ask for <span>{label}</span> and you get the left image. Correct: the right one.",
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
  b_red_k: "CI is red", b_red_m: "{n} tests failing", b_launch_m: "{n} worlds launched",
  b_merge_k: "Proven by tests", b_merge_m: "1 merged · {d} thrown away", b_none_k: "No world passed", b_none_m: "{c} tried · all thrown away",
  pause: "Pause", play: "Play", copy_pr: "Copy PR description", copied: "Copied", dl_patch: "Download patch",
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
