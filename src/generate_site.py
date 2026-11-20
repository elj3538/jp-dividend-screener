"""日本株 配当株 軍分けランキングのトップページ（index.html）および ranking.json を生成するモジュール。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))


def _compact_item(it: dict[str, Any]) -> dict[str, Any]:
    sc = it["scoring"]
    m = sc["metrics"]
    p = it["price"]
    return {
        "code": it["code"],
        "name": it["name"],
        "sector33": it.get("sector33", ""),
        "sector_group": it.get("sector_group", ""),
        "market": it.get("market", ""),
        "scale": it.get("scale", ""),
        "is_progressive": bool(it.get("is_progressive", False)),
        "is_financial": bool(sc.get("is_financial", False)),
        "model": sc.get("model", "general"),
        "price": p.get("current"),
        "price_date": p.get("date"),
        "market_cap_oku": m.get("market_cap_oku"),
        "returns": p.get("returns", {}),
        "selection_score": sc["selection_score"],
        "timing_score": sc["timing_score"],
        "perf_score": sc.get("perf_score"),
        "fin_score": sc.get("fin_score"),
        "cf_score": sc.get("cf_score"),
        "div_sust_score": sc.get("div_sust_score"),
        "sector_dev": sc.get("sector_dev"),
        "sector_dev_info": sc.get("sector_dev_info", ""),
        "tier": sc.get("tier", "―"),
        "tier_num": sc.get("tier_num", 0),
        "sector_grade": sc.get("sector_grade", "B"),
        "coverage": sc.get("coverage", "中"),
        "overall_rank": sc.get("overall_rank", 9999),
        "fwd_yield": m.get("fwd_yield"),
        "ttm_yield": m.get("ttm_yield"),
        "fwd_div": it.get("dividend", {}).get("fwd_div"),
        "div_cagr": m.get("div_cagr"),
        "consec_increase": m.get("consec_increase", 0),
        "consec_no_cut": m.get("consec_no_cut", 0),
        "payout_ratio": m.get("payout_ratio"),
        "is_loss_latest": bool(m.get("is_loss_latest", False)),
        "roe": m.get("roe"),
        "roa": m.get("roa"),
        "equity_ratio": m.get("equity_ratio"),
        "ocf_positive": bool(m.get("ocf_positive", False)),
        "fcf_positive": bool(m.get("fcf_positive", False)),
        "fcf_payout": m.get("fcf_payout"),
        "chowder": m.get("chowder"),
        "div_yield_range_pos": m.get("div_yield_range_pos"),
        "pe_rel_sector": m.get("pe_rel_sector"),
        "pbr_rel_sector": m.get("pbr_rel_sector"),
        "per_range_pos": m.get("per_range_pos"),
        "trailing_pe": m.get("trailing_pe"),
        "pbr": m.get("pbr"),
        "warnings": sc.get("warnings", []),
    }


def generate_site(
    items: list[dict[str, Any]],
    sector_stats: list[dict[str, Any]],
    dist_dir: Path,
    jp10y_yield: float = 1.50,
) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    price_dates = [it["price"].get("date") for it in items if it.get("price", {}).get("date")]
    latest_price_date = max(price_dates) if price_dates else now_jst[:10]

    compact = [_compact_item(it) for it in items]
    payload = {
        "generated_at": now_jst,
        "latest_price_date": latest_price_date,
        "jp10y_yield": jp10y_yield,
        "total_count": len(compact),
        "sector_stats": sector_stats,
        "items": compact,
    }
    (dist_dir / "ranking.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    t1_cnt = sum(1 for x in compact if x["tier_num"] == 1)
    t2_cnt = sum(1 for x in compact if x["tier_num"] == 2)
    t3_cnt = sum(1 for x in compact if x["tier_num"] == 3)
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>日本株 配当株 軍分けランキング</title>
<style>
:root {{
  --bg: #f6f8fb;
  --surface: #ffffff;
  --border: #dfe5ef;
  --text: #1b2432;
  --muted: #5f6c80;
  --accent: #1d5fd6;
  --accent-soft: #eaf1ff;
  --t1-bg: #e6f6ec; --t1-fg: #137333;
  --t2-bg: #eaf1ff; --t2-fg: #1d5fd6;
  --t3-bg: #f1f3f6; --t3-fg: #5f6c80;
  --good: #137333; --warn: #b06000; --bad: #c5221f;
  --row-hover: #f3f7ff;
}}
body.dark {{
  --bg: #0f141d;
  --surface: #18202c;
  --border: #2a3547;
  --text: #e8eef7;
  --muted: #9aa7bd;
  --accent: #5e9bff;
  --accent-soft: #1d2c44;
  --t1-bg: #133122; --t1-fg: #6ee79c;
  --t2-bg: #182b49; --t2-fg: #7ab3ff;
  --t3-bg: #232b38; --t3-fg: #9aa7bd;
  --good: #6ee79c; --warn: #fbbf24; --bad: #f87171;
  --row-hover: #1e293b;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", "Yu Gothic UI", sans-serif;
  background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.wrap {{ max-width: 1460px; margin: 0 auto; padding: 14px 16px 80px; }}
header {{
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;
  border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 12px;
}}
h1 {{ margin: 0; font-size: 20px; display: flex; align-items: center; gap: 8px; }}
.badge-sub {{ font-size: 11px; padding: 2px 7px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-weight: 600; }}
nav {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; font-size: 13px; }}
nav a.nav-btn {{
  padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text);
}}
nav a.nav-btn:hover {{ background: var(--accent-soft); text-decoration: none; }}
.theme-bar {{
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; color: var(--muted);
  margin-bottom: 10px;
}}
.theme-bar button {{
  border: 1px solid var(--border); background: var(--surface); color: var(--text);
  border-radius: 6px; padding: 3px 8px; cursor: pointer; font-size: 12px;
}}
.theme-bar button:hover {{ border-color: var(--accent); }}
.meta-line {{ font-size: 12px; color: var(--muted); margin-bottom: 12px; }}
.kpi-bar {{
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px;
}}
.kpi-btn {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 14px; cursor: pointer; color: var(--text); display: flex; align-items: baseline; gap: 6px;
}}
.kpi-btn .num {{ font-size: 18px; font-weight: 700; }}
.kpi-btn .lbl {{ font-size: 12px; color: var(--muted); }}
.kpi-btn.active {{ border-color: var(--accent); background: var(--accent-soft); }}
.toolbar {{
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px;
}}
.toolbar input[type=text] {{
  padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--surface); color: var(--text); min-width: 260px; font-size: 13px;
}}
.btn {{
  padding: 6px 11px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--surface); color: var(--text); cursor: pointer; font-size: 12.5px;
}}
.btn:hover {{ border-color: var(--accent); }}
.btn-primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.btn-primary:hover {{ opacity: .92; }}
details.panel {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 14px; margin-bottom: 12px;
}}
details.panel > summary {{
  cursor: pointer; font-weight: 700; font-size: 14px; user-select: none;
}}
.filter-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 12px;
}}
.filter-box {{
  border: 1px solid var(--border); border-radius: 6px; padding: 10px; background: var(--bg);
}}
.filter-box h4 {{ margin: 0 0 8px; font-size: 13px; color: var(--accent); }}
.f-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 6px; font-size: 12px; }}
.f-row label {{ display: inline-flex; align-items: center; gap: 3px; cursor: pointer; }}
.f-row input[type=number] {{
  width: 72px; padding: 3px 5px; border: 1px solid var(--border); border-radius: 4px;
  background: var(--surface); color: var(--text); font-size: 12px;
}}
.sec-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  margin-bottom: 16px; overflow: hidden;
}}
.sec-head {{
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px;
  padding: 10px 14px; background: var(--accent-soft); border-bottom: 1px solid var(--border);
}}
.sec-head h2 {{ margin: 0; font-size: 15px; display: flex; align-items: center; gap: 8px; }}
.grade {{
  display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 12px; font-weight: 700;
}}
.grade-A {{ background: #137333; color: #fff; }}
.grade-B {{ background: #1d5fd6; color: #fff; }}
.grade-C {{ background: #64748b; color: #fff; }}
.tbl-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; white-space: nowrap; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--border); text-align: right; }}
th {{ background: var(--bg); color: var(--muted); font-weight: 600; position: sticky; top: 0; user-select: none; }}
th.left, td.left {{ text-align: left; }}
th.center, td.center {{ text-align: center; }}
th.sortable {{ cursor: pointer; }}
th.sortable:hover {{ color: var(--accent); }}
tbody tr:hover {{ background: var(--row-hover); }}
.tier-badge {{ display: inline-block; padding: 1px 6px; border-radius: 4px; font-weight: 700; font-size: 11.5px; }}
.t1 {{ background: var(--t1-bg); color: var(--t1-fg); }}
.t2 {{ background: var(--t2-bg); color: var(--t2-fg); }}
.t3 {{ background: var(--t3-bg); color: var(--t3-fg); }}
.sc-good {{ color: var(--good); font-weight: 700; }}
.sc-warn {{ color: var(--warn); font-weight: 600; }}
.sc-bad {{ color: var(--bad); font-weight: 600; }}
.dev-sub {{ display: block; font-size: 10px; color: var(--muted); font-weight: 400; }}
.prog-tag {{ font-size: 10px; padding: 1px 4px; border-radius: 3px; background: var(--t1-bg); color: var(--t1-fg); margin-left: 4px; }}
.warn-icon {{ cursor: help; margin-left: 4px; }}
.ret-col {{ display: none; }}
.show-ret .ret-col {{ display: table-cell; }}
.pos {{ color: var(--good); }}
.neg {{ color: var(--bad); }}
.floating-bar {{
  position: fixed; bottom: 0; left: 0; right: 0; background: var(--surface);
  border-top: 1px solid var(--border); padding: 8px 16px; display: none;
  justify-content: center; gap: 12px; align-items: center; z-index: 99; box-shadow: 0 -2px 10px rgba(0,0,0,.08);
}}
.floating-bar.show {{ display: flex; }}
.toast {{
  position: fixed; bottom: 56px; right: 16px; background: #1e293b; color: #fff;
  padding: 8px 14px; border-radius: 6px; font-size: 13px; display: none; z-index: 120;
}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>日本株 配当株 軍分けランキング <span class="badge-sub">東証プライム・スタンダード / 13業種</span></h1>
    <nav>
      <a class="nav-btn" href="index.html">ランキング</a>
      <a class="nav-btn" href="watchlist.html">☆ ウォッチリスト</a>
      <a class="nav-btn" href="portfolio.html">💼 ポートフォリオ</a>
      <a class="nav-btn" href="guide.html">使い方・見方</a>
      <a class="nav-btn" href="terms.html">利用規約</a>
    </nav>
  </header>

  <div class="theme-bar">
    <span>配色:</span>
    <button onclick="toggleDark()">🌙 ダーク切替</button>
    <button onclick="setAccent('#1d5fd6','#eaf1ff')">標準ブルー</button>
    <button onclick="setAccent('#0f766e','#e6f7f5')">エメラルド</button>
    <button onclick="setAccent('#7c3aed','#f3ebff')">バイオレット</button>
    <button onclick="setAccent('#b45309','#fef3e2')">アンバー</button>
    <button onclick="resetTheme()">↺ 標準に戻す</button>
  </div>

  <div class="meta-line">
    生成: {now_jst} ｜ 株価終値日: {latest_price_date} ｜ 日本10年国債利回り: {jp10y_yield:.2f}% ｜
    スクリーン条件: 直近1年実績利回り≥2.0%・時価総額≥300億円・直近5年減配なし（累進配当/DOE例外）
  </div>

  <div class="kpi-bar">
    <button class="kpi-btn active" id="kpi-all" onclick="setTierFilter(0)"><span class="num" id="cnt-all">{len(compact)}</span><span class="lbl">銘柄</span></button>
    <button class="kpi-btn" id="kpi-1" onclick="setTierFilter(1)"><span class="num" id="cnt-1">{t1_cnt}</span><span class="lbl">1軍</span></button>
    <button class="kpi-btn" id="kpi-2" onclick="setTierFilter(2)"><span class="num" id="cnt-2">{t2_cnt}</span><span class="lbl">2軍</span></button>
    <button class="kpi-btn" id="kpi-3" onclick="setTierFilter(3)"><span class="num" id="cnt-3">{t3_cnt}</span><span class="lbl">3軍</span></button>
    <span style="font-size:12px;color:var(--muted);">※クリックでその軍だけ表示（再クリックで解除）</span>
  </div>

  <div class="toolbar">
    <input type="text" id="q" placeholder="コード・銘柄名・業種で検索（例: 8058 / 商社 / 銀行）" oninput="applyFilters()">
    <button class="btn" onclick="clearSearch()">クリア</button>
    <button class="btn" onclick="toggleReturns()">📈 騰落率を展開/収納</button>
    <button class="btn" onclick="exportCSV()">⬇ 表示中をCSV出力</button>
    <button class="btn" onclick="copyTSV()">📋 クリップボードにコピー</button>
    <span id="filtered-status" style="font-size:12px;color:var(--muted);margin-left:auto;"></span>
  </div>

  <details class="panel" id="screener-panel">
    <summary>🔍 詳しい条件で絞り込む（URL自動反映・ブラウザ保存）</summary>
    <div class="filter-grid">
      <div class="filter-box">
        <h4>① 銘柄選定（質・持続力）</h4>
        <div class="f-row">選定スコア <input type="number" id="f-sel-min" placeholder="85" onchange="applyFilters()"> 以上</div>
        <div class="f-row">業種内偏差値 <input type="number" id="f-dev-min" placeholder="55" onchange="applyFilters()"> 以上</div>
        <div class="f-row">増配率(%) <input type="number" step="0.5" id="f-dcagr-min" placeholder="3" onchange="applyFilters()"> 以上</div>
        <div class="f-row">連続増配年 <input type="number" id="f-cinc-min" placeholder="5" onchange="applyFilters()"> 年以上</div>
        <div class="f-row">連続非減配 <input type="number" id="f-cnocut-min" placeholder="10" onchange="applyFilters()"> 年以上</div>
        <div class="f-row">配当性向(%) <input type="number" id="f-payout-max" placeholder="60" onchange="applyFilters()"> 以下</div>
        <div class="f-row">ROE(%) <input type="number" step="0.5" id="f-roe-min" placeholder="10" onchange="applyFilters()"> 以上 / ROA(%) <input type="number" step="0.5" id="f-roa-min" placeholder="5" onchange="applyFilters()"> 以上</div>
        <div class="f-row">
          <label><input type="checkbox" id="f-ocf-pos" onchange="applyFilters()"> 営業CF黒字のみ</label>
          <label><input type="checkbox" id="f-fcf-pos" onchange="applyFilters()"> FCF黒字のみ</label>
          <label><input type="checkbox" id="f-prog-only" onchange="applyFilters()"> 累進配当/DOE宣言のみ</label>
        </div>
      </div>
      <div class="filter-box">
        <h4>② 買い時（割安度・利回り）</h4>
        <div class="f-row">買い時スコア <input type="number" id="f-tim-min" placeholder="82" onchange="applyFilters()"> 以上</div>
        <div class="f-row">予想利回り(%) <input type="number" step="0.1" id="f-yld-min" placeholder="3.5" onchange="applyFilters()"> 以上</div>
        <div class="f-row">Chowder(%) <input type="number" step="0.5" id="f-chw-min" placeholder="10" onchange="applyFilters()"> 以上</div>
        <div class="f-row">利回りレンジ位置(%) <input type="number" id="f-drng-min" placeholder="60" onchange="applyFilters()"> 以上</div>
        <div class="f-row">PER対業種 <input type="number" step="0.05" id="f-perel-max" placeholder="1.0" onchange="applyFilters()"> 倍以下</div>
        <div class="f-row">PBR対業種 <input type="number" step="0.05" id="f-pbrel-max" placeholder="1.0" onchange="applyFilters()"> 倍以下</div>
      </div>
      <div class="filter-box">
        <h4>③ 銘柄属性・業種</h4>
        <div class="f-row">時価総額(億円) <input type="number" id="f-cap-min" placeholder="1000" onchange="applyFilters()"> 以上</div>
        <div class="f-row">終値(円) <input type="number" id="f-prc-max" placeholder="5000" onchange="applyFilters()"> 以下</div>
        <div class="f-row">業種級:
          <label><input type="checkbox" class="f-grade" value="A" onchange="applyFilters()"> A</label>
          <label><input type="checkbox" class="f-grade" value="B" onchange="applyFilters()"> B</label>
          <label><input type="checkbox" class="f-grade" value="C" onchange="applyFilters()"> C</label>
        </div>
        <div class="f-row">カバレッジ:
          <label><input type="checkbox" class="f-cov" value="高" onchange="applyFilters()"> 高</label>
          <label><input type="checkbox" class="f-cov" value="中" onchange="applyFilters()"> 中</label>
          <label><input type="checkbox" class="f-cov" value="低" onchange="applyFilters()"> 低</label>
        </div>
        <div class="f-row">区分:
          <label><input type="radio" name="f-fintype" value="all" checked onchange="applyFilters()"> すべて</label>
          <label><input type="radio" name="f-fintype" value="general" onchange="applyFilters()"> 一般企業のみ</label>
          <label><input type="radio" name="f-fintype" value="financial" onchange="applyFilters()"> 金融のみ</label>
        </div>
        <div class="f-row">
          <button class="btn" onclick="resetFilters()">条件をクリア</button>
        </div>
      </div>
    </div>
    <div style="margin-top:8px;font-size:12px;" id="group-checks"></div>
  </details>

  <details class="panel">
    <summary>💾 バックアップ（CSV書き出し・読み込み復元）</summary>
    <p style="font-size:12px;color:var(--muted);margin:8px 0;">
      絞り込み条件・ウォッチリスト・ポートフォリオ保有記録を1つのCSVにまとめて保存・復元できます。
    </p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
      <button class="btn btn-primary" onclick="backupCSV()">CSVで書き出す</button>
      <label class="btn">CSVを読み込んで復元 <input type="file" accept=".csv" style="display:none;" onchange="restoreCSV(event)"></label>
    </div>
  </details>

  <details class="panel" id="top50-panel">
    <summary>🏆 全体 選定スコア 上位50（業種横断）</summary>
    <div class="tbl-wrap" style="margin-top:10px;" id="top50-container"></div>
  </details>

  <div id="sections-container"></div>
</div>

<div class="floating-bar" id="floating-bar">
  <span id="sel-summary" style="font-size:13px;font-weight:600;"></span>
  <button class="btn btn-primary" onclick="commitWatchlist()">☆ ウォッチリストへ追加</button>
  <button class="btn btn-primary" onclick="commitPortfolio()">💼 ポートフォリオへ追加</button>
  <button class="btn" onclick="clearSelections()">選択解除</button>
</div>
<div class="toast" id="toast"></div>

<script>
const RAW_DATA = {data_json};
const ALL_ITEMS = RAW_DATA.items || [];
const SECTOR_STATS = RAW_DATA.sector_stats || [];
const LS_WL = "jp_div_screener_watchlist";
const LS_PF = "jp_div_screener_portfolio";
const LS_THEME = "jp_div_screener_theme";

let tierFilter = 0;
let showReturns = false;
let sortKey = "selection_score";
let sortAsc = false;
let filteredItems = [...ALL_ITEMS];
const checkedWL = new Set();
const checkedPF = new Set();

function toast(msg) {{
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(window._tt);
  window._tt = setTimeout(() => t.style.display = "none", 2600);
}}

function toggleDark() {{
  document.body.classList.toggle("dark");
  saveTheme();
}}
function setAccent(acc, soft) {{
  document.documentElement.style.setProperty("--accent", acc);
  document.documentElement.style.setProperty("--accent-soft", soft);
  saveTheme();
}}
function resetTheme() {{
  document.body.classList.remove("dark");
  document.documentElement.style.removeProperty("--accent");
  document.documentElement.style.removeProperty("--accent-soft");
  localStorage.removeItem(LS_THEME);
}}
function saveTheme() {{
  localStorage.setItem(LS_THEME, JSON.stringify({{
    dark: document.body.classList.contains("dark"),
    accent: document.documentElement.style.getPropertyValue("--accent"),
    soft: document.documentElement.style.getPropertyValue("--accent-soft"),
  }}));
}}
function loadTheme() {{
  try {{
    const t = JSON.parse(localStorage.getItem(LS_THEME) || "null");
    if (!t) return;
    if (t.dark) document.body.classList.add("dark");
    if (t.accent) document.documentElement.style.setProperty("--accent", t.accent);
    if (t.soft) document.documentElement.style.setProperty("--accent-soft", t.soft);
  }} catch(e) {{}}
}}

function fmtNum(v, d=1, suf="") {{
  if (v === null || v === undefined || Number.isNaN(v)) return "―";
  return Number(v).toLocaleString("ja-JP", {{minimumFractionDigits: d, maximumFractionDigits: d}}) + suf;
}}
function fmtYen(v) {{
  if (v === null || v === undefined) return "―";
  return "¥" + Math.round(v).toLocaleString("ja-JP");
}}
function fmtRet(v) {{
  if (v === null || v === undefined) return "―";
  const cls = v > 0 ? "pos" : (v < 0 ? "neg" : "");
  return `<span class="${{cls}}">${{v > 0 ? "+" : ""}}${{v.toFixed(1)}}%</span>`;
}}
function scoreCls(v, hi, mid) {{
  if (v === null || v === undefined) return "";
  return v >= hi ? "sc-good" : (v >= mid ? "" : "sc-bad");
}}
function tierBadge(t, tn) {{
  if (tn === 1) return `<span class="tier-badge t1">1軍</span>`;
  if (tn === 2) return `<span class="tier-badge t2">2軍</span>`;
  if (tn === 3) return `<span class="tier-badge t3">3軍</span>`;
  return `<span class="tier-badge t3">―</span>`;
}}

function initGroupChecks() {{
  const box = document.getElementById("group-checks");
  const groups = SECTOR_STATS.map(s => s.sector_group);
  box.innerHTML = "<strong>業種グループ: </strong>" + groups.map(g =>
    `<label style="margin-right:8px;display:inline-flex;align-items:center;gap:3px;"><input type="checkbox" class="f-grp" value="${{g}}" onchange="applyFilters()">${{g}}</label>`
  ).join("");
}}

function setTierFilter(t) {{
  tierFilter = (tierFilter === t && t !== 0) ? 0 : t;
  [0,1,2,3].forEach(k => {{
    const el = document.getElementById("kpi-" + (k === 0 ? "all" : k));
    if (el) el.classList.toggle("active", tierFilter === k);
  }});
  applyFilters();
}}
function clearSearch() {{
  document.getElementById("q").value = "";
  applyFilters();
}}
function toggleReturns() {{
  showReturns = !showReturns;
  document.body.classList.toggle("show-ret", showReturns);
}}
function resetFilters() {{
  ["f-sel-min","f-dev-min","f-dcagr-min","f-cinc-min","f-cnocut-min","f-payout-max","f-roe-min","f-roa-min",
   "f-tim-min","f-yld-min","f-chw-min","f-drng-min","f-perel-max","f-pbrel-max","f-cap-min","f-prc-max"].forEach(id => {{
    document.getElementById(id).value = "";
  }});
  ["f-ocf-pos","f-fcf-pos","f-prog-only"].forEach(id => document.getElementById(id).checked = false);
  document.querySelectorAll(".f-grade,.f-cov,.f-grp").forEach(el => el.checked = false);
  document.querySelector('input[name="f-fintype"][value="all"]').checked = true;
  tierFilter = 0;
  setTierFilter(0);
}}

function numVal(id) {{
  const s = document.getElementById(id).value.trim();
  return s === "" ? null : Number(s);
}}

function applyFilters() {{
  const q = document.getElementById("q").value.trim().toLowerCase();
  const selMin = numVal("f-sel-min");
  const devMin = numVal("f-dev-min");
  const dcagrMin = numVal("f-dcagr-min");
  const cincMin = numVal("f-cinc-min");
  const cnocutMin = numVal("f-cnocut-min");
  const payoutMax = numVal("f-payout-max");
  const roeMin = numVal("f-roe-min");
  const roaMin = numVal("f-roa-min");
  const ocfPos = document.getElementById("f-ocf-pos").checked;
  const fcfPos = document.getElementById("f-fcf-pos").checked;
  const progOnly = document.getElementById("f-prog-only").checked;
  const timMin = numVal("f-tim-min");
  const yldMin = numVal("f-yld-min");
  const chwMin = numVal("f-chw-min");
  const drngMin = numVal("f-drng-min");
  const perelMax = numVal("f-perel-max");
  const pbrelMax = numVal("f-pbrel-max");
  const capMin = numVal("f-cap-min");
  const prcMax = numVal("f-prc-max");
  const grades = [...document.querySelectorAll(".f-grade:checked")].map(e => e.value);
  const covs = [...document.querySelectorAll(".f-cov:checked")].map(e => e.value);
  const grps = [...document.querySelectorAll(".f-grp:checked")].map(e => e.value);
  const finType = document.querySelector('input[name="f-fintype"]:checked').value;

  filteredItems = ALL_ITEMS.filter(x => {{
    if (tierFilter && x.tier_num !== tierFilter) return false;
    if (q) {{
      const hay = (x.code + " " + x.name + " " + x.sector33 + " " + x.sector_group).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    if (selMin !== null && (x.selection_score ?? -999) < selMin) return false;
    if (devMin !== null && (x.sector_dev ?? -999) < devMin) return false;
    if (dcagrMin !== null && (x.div_cagr ?? -999) < dcagrMin) return false;
    if (cincMin !== null && (x.consec_increase ?? 0) < cincMin) return false;
    if (cnocutMin !== null && (x.consec_no_cut ?? 0) < cnocutMin) return false;
    if (payoutMax !== null && (x.payout_ratio === null || x.payout_ratio > payoutMax)) return false;
    if (roeMin !== null && (x.roe ?? -999) < roeMin) return false;
    if (roaMin !== null && (x.roa ?? -999) < roaMin) return false;
    if (ocfPos && !x.ocf_positive) return false;
    if (fcfPos && !x.fcf_positive) return false;
    if (progOnly && !x.is_progressive) return false;
    if (timMin !== null && (x.timing_score ?? -999) < timMin) return false;
    if (yldMin !== null && (x.fwd_yield ?? -999) < yldMin) return false;
    if (chwMin !== null && (x.chowder ?? -999) < chwMin) return false;
    if (drngMin !== null && (x.div_yield_range_pos ?? -999) < drngMin) return false;
    if (perelMax !== null && (x.pe_rel_sector === null || x.pe_rel_sector > perelMax)) return false;
    if (pbrelMax !== null && (x.pbr_rel_sector === null || x.pbr_rel_sector > pbrelMax)) return false;
    if (capMin !== null && (x.market_cap_oku ?? 0) < capMin) return false;
    if (prcMax !== null && (x.price === null || x.price > prcMax)) return false;
    if (grades.length && !grades.includes(x.sector_grade)) return false;
    if (covs.length && !covs.includes(x.coverage)) return false;
    if (grps.length && !grps.includes(x.sector_group)) return false;
    if (finType === "general" && x.is_financial) return false;
    if (finType === "financial" && !x.is_financial) return false;
    return true;
  }});

  document.getElementById("filtered-status").textContent = `表示中: ${{filteredItems.length}} / ${{ALL_ITEMS.length}} 銘柄`;
  renderAll();
}}

function sortBy(key) {{
  if (sortKey === key) sortAsc = !sortAsc;
  else {{ sortKey = key; sortAsc = false; }}
  renderAll();
}}

function getSortVal(x, key) {{
  if (key.startsWith("ret_")) return x.returns ? x.returns[key.slice(4)] : null;
  return x[key];
}}

function buildRow(x, idx, showGroup=false) {{
  const r = x.returns || {{}};
  const warnHtml = (x.warnings && x.warnings.length)
    ? `<span class="warn-icon" title="${{x.warnings.join(" / ")}}">⚠</span>` : "";
  const progHtml = x.is_progressive ? `<span class="prog-tag" title="累進配当・DOE宣言銘柄">累進</span>` : "";
  const devHtml = x.sector_dev !== null && x.sector_dev !== undefined
    ? `<span class="dev-sub">偏差値${{x.sector_dev.toFixed(0)}}</span>` : "";
  return `<tr>
    <td class="center"><input type="checkbox" ${{checkedWL.has(x.code)?"checked":""}} onchange="toggleSel('wl','${{x.code}}',this.checked)"></td>
    <td class="center"><input type="checkbox" ${{checkedPF.has(x.code)?"checked":""}} onchange="toggleSel('pf','${{x.code}}',this.checked)"></td>
    ${{showGroup ? `<td class="center">${{idx+1}}</td>` : ""}}
    <td class="center">${{tierBadge(x.tier, x.tier_num)}}</td>
    <td class="left"><a href="reports/${{x.code}}.html" style="font-weight:700;">${{x.code}}</a></td>
    <td class="left"><a href="reports/${{x.code}}.html">${{x.name}}</a>${{progHtml}}${{warnHtml}}</td>
    <td class="left" style="color:var(--muted);font-size:11.5px;">${{showGroup ? x.sector_group : x.sector33}}</td>
    <td>${{fmtYen(x.price)}}</td>
    <td class="ret-col">${{fmtRet(r.D)}}</td>
    <td class="ret-col">${{fmtRet(r.W)}}</td>
    <td class="ret-col">${{fmtRet(r.M)}}</td>
    <td class="ret-col">${{fmtRet(r["3M"])}}</td>
    <td class="ret-col">${{fmtRet(r["6M"])}}</td>
    <td class="ret-col">${{fmtRet(r.Y)}}</td>
    <td class="${{scoreCls(x.selection_score, 85, 68)}}">${{fmtNum(x.selection_score, 1)}}${{devHtml}}</td>
    <td class="${{scoreCls(x.timing_score, 98, 82)}}">${{fmtNum(x.timing_score, 1)}}</td>
    <td class="${{scoreCls(x.fwd_yield, 3.5, 2.0)}}">${{fmtNum(x.fwd_yield, 2, "%")}}</td>
    <td>${{fmtNum(x.div_cagr, 1, "%")}}</td>
    <td>${{fmtNum(x.roe, 1, "%")}}</td>
    <td>${{fmtNum(x.roa, 1, "%")}}</td>
    <td class="center">${{x.coverage}}</td>
  </tr>`;
}}

function buildTableHead(showGroup=false) {{
  return `<thead><tr>
    <th class="center" title="ウォッチリストに追加">☆</th>
    <th class="center" title="ポートフォリオに追加">💼</th>
    ${{showGroup ? `<th class="center">#</th>` : ""}}
    <th class="center sortable" onclick="sortBy('tier_num')">軍▼</th>
    <th class="left sortable" onclick="sortBy('code')">コード▼</th>
    <th class="left">銘柄</th>
    <th class="left">${{showGroup ? "グループ" : "業種"}}</th>
    <th class="sortable" onclick="sortBy('price')">終値▼</th>
    <th class="ret-col sortable" onclick="sortBy('ret_D')">D▼</th>
    <th class="ret-col sortable" onclick="sortBy('ret_W')">W▼</th>
    <th class="ret-col sortable" onclick="sortBy('ret_M')">M▼</th>
    <th class="ret-col sortable" onclick="sortBy('ret_3M')">3M▼</th>
    <th class="ret-col sortable" onclick="sortBy('ret_6M')">6M▼</th>
    <th class="ret-col sortable" onclick="sortBy('ret_Y')">Y▼</th>
    <th class="sortable" onclick="sortBy('selection_score')" title="配当株としての質（0〜110）と業種内偏差値">選定▼</th>
    <th class="sortable" onclick="sortBy('timing_score')" title="今の株価の割安度（0〜110）">買い時▼</th>
    <th class="sortable" onclick="sortBy('fwd_yield')" title="予想配当利回り">利回り▼</th>
    <th class="sortable" onclick="sortBy('div_cagr')" title="5年増配率CAGR">増配▼</th>
    <th class="sortable" onclick="sortBy('roe')" title="自己資本利益率">ROE▼</th>
    <th class="sortable" onclick="sortBy('roa')" title="総資産利益率（表示専用）">ROA▼</th>
    <th class="center">カバレッジ</th>
  </tr></thead>`;
}}

function sortList(arr) {{
  return [...arr].sort((a, b) => {{
    let va = getSortVal(a, sortKey);
    let vb = getSortVal(b, sortKey);
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (typeof va === "string") return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  }});
}}

function renderAll() {{
  // Top 50
  const top50 = [...filteredItems].sort((a,b) => b.selection_score - a.selection_score).slice(0, 50);
  document.getElementById("top50-container").innerHTML =
    `<table>${{buildTableHead(true)}}<tbody>${{top50.map((x,i) => buildRow(x, i, true)).join("")}}</tbody></table>`;

  // By sector group
  const byGrp = {{}};
  filteredItems.forEach(x => {{
    (byGrp[x.sector_group] = byGrp[x.sector_group] || []).push(x);
  }});
  const secHtml = SECTOR_STATS.map(st => {{
    const rows = byGrp[st.sector_group];
    if (!rows || !rows.length) return "";
    const sorted = sortList(rows);
    return `<section class="sec-card">
      <div class="sec-head">
        <h2>${{st.sector_group}} <span class="grade grade-${{st.grade}}">業種級 ${{st.grade}}</span></h2>
        <span style="font-size:12px;color:var(--muted);">中央値 ${{st.median_score.toFixed(1)}} ／ 表示 ${{sorted.length}}銘柄（全${{st.count}}）</span>
      </div>
      <div class="tbl-wrap">
        <table>${{buildTableHead(false)}}<tbody>${{sorted.map((x,i) => buildRow(x, i, false)).join("")}}</tbody></table>
      </div>
    </section>`;
  }}).join("");
  document.getElementById("sections-container").innerHTML = secHtml || `<p style="padding:20px;color:var(--muted);">条件に一致する銘柄がありません。</p>`;
}}

function toggleSel(kind, code, checked) {{
  const set = kind === "wl" ? checkedWL : checkedPF;
  if (checked) set.add(code); else set.delete(code);
  const bar = document.getElementById("floating-bar");
  const total = checkedWL.size + checkedPF.size;
  bar.classList.toggle("show", total > 0);
  document.getElementById("sel-summary").textContent = `選択中: ☆ ${{checkedWL.size}}件 / 💼 ${{checkedPF.size}}件`;
}}
function clearSelections() {{
  checkedWL.clear(); checkedPF.clear();
  document.getElementById("floating-bar").classList.remove("show");
  renderAll();
}}
function commitWatchlist() {{
  if (!checkedWL.size) return toast("☆にチェックを入れてください");
  const cur = JSON.parse(localStorage.getItem(LS_WL) || "[]");
  const merged = [...new Set([...cur, ...checkedWL])];
  localStorage.setItem(LS_WL, JSON.stringify(merged));
  toast(`ウォッチリストに ${{checkedWL.size}} 銘柄を追加しました`);
  checkedWL.clear();
  toggleSel("wl", "", false);
  renderAll();
}}
function commitPortfolio() {{
  if (!checkedPF.size) return toast("💼にチェックを入れてください");
  const cur = JSON.parse(localStorage.getItem(LS_PF) || "[]");
  const existing = new Set(cur.map(x => x.code));
  let added = 0;
  checkedPF.forEach(code => {{
    if (!existing.has(code)) {{
      const it = ALL_ITEMS.find(x => x.code === code);
      cur.push({{ code, shares: 100, avg_cost: it ? (it.price || 0) : 0, section: "メイン" }});
      added++;
    }}
  }});
  localStorage.setItem(LS_PF, JSON.stringify(cur));
  toast(`ポートフォリオに ${{added}} 銘柄を追加しました`);
  checkedPF.clear();
  toggleSel("pf", "", false);
  renderAll();
}}

function exportCSV() {{
  const cols = ["code","name","sector_group","sector33","tier","price","selection_score","sector_dev","timing_score","fwd_yield","div_cagr","consec_increase","consec_no_cut","payout_ratio","roe","roa","coverage"];
  const lines = [cols.join(",")];
  filteredItems.forEach(x => {{
    lines.push(cols.map(c => `"${{String(x[c] ?? "").replace(/"/g,'""')}}"`).join(","));
  }});
  const blob = new Blob(["\\uFEFF" + lines.join("\\n")], {{type: "text/csv;charset=utf-8"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "jp_dividend_ranking.csv";
  a.click();
}}
function copyTSV() {{
  const cols = ["code","name","sector_group","tier","price","selection_score","timing_score","fwd_yield","div_cagr","roe","roa"];
  const lines = [cols.join("\\t"), ...filteredItems.map(x => cols.map(c => x[c] ?? "").join("\\t"))];
  navigator.clipboard.writeText(lines.join("\\n")).then(() => toast("クリップボードにコピーしました"));
}}

function backupCSV() {{
  const payload = {{
    type: "jp_dividend_screener_backup_v1",
    watchlist: JSON.parse(localStorage.getItem(LS_WL) || "[]"),
    portfolio: JSON.parse(localStorage.getItem(LS_PF) || "[]"),
  }};
  const today = new Date().toISOString().slice(0, 10);
  const blob = new Blob(["\\uFEFFkey,value\\nbackup_json," + JSON.stringify(JSON.stringify(payload))], {{type: "text/csv;charset=utf-8"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `配当株（日株）${{today}}.csv`;
  a.click();
}}
function restoreCSV(ev) {{
  const file = ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {{
    try {{
      const line = reader.result.split(/\\r?\\n/).find(l => l.startsWith("backup_json,"));
      if (!line) throw new Error("形式不正");
      const raw = JSON.parse(line.slice("backup_json,".length));
      const obj = JSON.parse(raw);
      if (obj.type !== "jp_dividend_screener_backup_v1") throw new Error("日株用バックアップではありません");
      localStorage.setItem(LS_WL, JSON.stringify(obj.watchlist || []));
      localStorage.setItem(LS_PF, JSON.stringify(obj.portfolio || []));
      toast("バックアップを復元しました");
    }} catch(e) {{
      toast("復元に失敗しました: " + e.message);
    }}
  }};
  reader.readAsText(file, "utf-8");
}}

loadTheme();
initGroupChecks();
applyFilters();
</script>
</body>
</html>
"""
    index_path = dist_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path
