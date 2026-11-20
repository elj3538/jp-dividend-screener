"""補助ページ（watchlist.html / portfolio.html / guide.html / terms.html）を生成するモジュール。"""

from __future__ import annotations

from pathlib import Path

BASE_STYLE = """
:root {
  --bg: #f6f8fb; --surface: #ffffff; --border: #dfe5ef; --text: #1b2432; --muted: #5f6c80;
  --accent: #1d5fd6; --accent-soft: #eaf1ff; --good: #137333; --bad: #c5221f;
}
body.dark {
  --bg: #0f141d; --surface: #18202c; --border: #2a3547; --text: #e8eef7; --muted: #9aa7bd;
  --accent: #5e9bff; --accent-soft: #1d2c44; --good: #6ee79c; --bad: #f87171;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.65; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrap { max-width: 1180px; margin: 0 auto; padding: 16px 16px 60px; }
header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 16px; }
h1 { margin: 0; font-size: 20px; }
nav { display: flex; gap: 8px; flex-wrap: wrap; font-size: 13px; }
nav a { padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 14px; }
.btn { padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); cursor: pointer; font-size: 13px; }
.btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 7px 8px; border-bottom: 1px solid var(--border); text-align: right; }
th { background: var(--bg); color: var(--muted); }
th.left, td.left { text-align: left; }
input[type=number], input[type=text] { padding: 4px 6px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface); color: var(--text); }
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px; }
.kpi-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.kpi-card .v { font-size: 22px; font-weight: 800; color: var(--accent); }
.kpi-card .l { font-size: 12px; color: var(--muted); }
.pos { color: var(--good); font-weight: 600; }
.neg { color: var(--bad); font-weight: 600; }
"""

THEME_SCRIPT = """
<script>
try {
  const t = JSON.parse(localStorage.getItem("jp_div_screener_theme") || "null");
  if (t && t.dark) document.body.classList.add("dark");
} catch(e) {}
</script>
"""


def _nav_header(title: str) -> str:
    return f"""<header>
  <h1>{title}</h1>
  <nav>
    <a href="index.html">ランキング</a>
    <a href="watchlist.html">☆ ウォッチリスト</a>
    <a href="portfolio.html">💼 ポートフォリオ</a>
    <a href="guide.html">使い方・見方</a>
    <a href="terms.html">利用規約</a>
  </nav>
</header>"""


def generate_auxiliary_pages(dist_dir: Path, jp10y_yield: float = 1.50) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 1. watchlist.html
    wl_html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ウォッチリスト｜日本株 配当株 軍分けランキング</title><style>{BASE_STYLE}</style></head>
<body><div class="wrap">
{_nav_header("☆ ウォッチリスト（日本配当株）")}
<div class="card">
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
    <input type="text" id="add-code" placeholder="銘柄コードを追加（例: 8058）">
    <button class="btn btn-primary" onclick="addCode()">追加</button>
    <button class="btn" onclick="clearAll()">すべて削除</button>
  </div>
  <div style="overflow-x:auto;">
    <table>
      <thead><tr><th class="left">コード</th><th class="left">銘柄</th><th class="left">グループ</th><th>軍</th><th>終値</th><th>選定</th><th>買い時</th><th>予想利回り</th><th>増配率</th><th>操作</th></tr></thead>
      <tbody id="wl-body"></tbody>
    </table>
  </div>
</div>
</div>
<script>
const LS_WL = "jp_div_screener_watchlist";
let MAP = {{}};
async function init() {{
  const res = await fetch("ranking.json");
  const data = await res.json();
  (data.items || []).forEach(x => MAP[x.code] = x);
  render();
}}
function getList() {{ return JSON.parse(localStorage.getItem(LS_WL) || "[]"); }}
function saveList(arr) {{ localStorage.setItem(LS_WL, JSON.stringify([...new Set(arr)])); render(); }}
function addCode() {{
  const c = document.getElementById("add-code").value.trim();
  if (!c) return;
  const arr = getList(); arr.push(c); saveList(arr);
  document.getElementById("add-code").value = "";
}}
function removeCode(c) {{ saveList(getList().filter(x => x !== c)); }}
function clearAll() {{ if (confirm("ウォッチリストを空にしますか？")) saveList([]); }}
function render() {{
  const arr = getList();
  const tb = document.getElementById("wl-body");
  if (!arr.length) {{ tb.innerHTML = "<tr><td colspan='10' style='text-align:center;color:var(--muted);'>登録銘柄がありません。ランキング表の☆から追加できます。</td></tr>"; return; }}
  tb.innerHTML = arr.map(c => {{
    const x = MAP[c];
    if (!x) return `<tr><td class="left">${{c}}</td><td class="left" colspan="8" style="color:var(--muted);">現在スクリーニング対象外</td><td><button class="btn" onclick="removeCode('${{c}}')">削除</button></td></tr>`;
    return `<tr>
      <td class="left"><a href="reports/${{x.code}}.html"><strong>${{x.code}}</strong></a></td>
      <td class="left"><a href="reports/${{x.code}}.html">${{x.name}}</a></td>
      <td class="left">${{x.sector_group}}</td>
      <td>${{x.tier}}</td>
      <td>¥${{Math.round(x.price||0).toLocaleString("ja-JP")}}</td>
      <td>${{x.selection_score.toFixed(1)}}</td>
      <td>${{x.timing_score.toFixed(1)}}</td>
      <td>${{x.fwd_yield !== null ? x.fwd_yield.toFixed(2)+"%" : "―"}}</td>
      <td>${{x.div_cagr !== null ? x.div_cagr.toFixed(1)+"%" : "―"}}</td>
      <td><button class="btn" onclick="removeCode('${{c}}')">削除</button></td>
    </tr>`;
  }}).join("");
}}
init();
</script>{THEME_SCRIPT}</body></html>"""
    (dist_dir / "watchlist.html").write_text(wl_html, encoding="utf-8")

    # 2. portfolio.html（円建て年間予想配当シミュレーター付き）
    pf_html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ポートフォリオ｜日本株 配当株 軍分けランキング</title><style>{BASE_STYLE}</style></head>
<body><div class="wrap">
{_nav_header("💼 ポートフォリオ ＆ 年間予想配当シミュレーター（円建て）")}
<div class="kpi-grid">
  <div class="kpi-card"><div class="l">評価額合計</div><div class="v" id="k-val">¥0</div></div>
  <div class="kpi-card"><div class="l">評価損益</div><div class="v" id="k-pnl">¥0</div></div>
  <div class="kpi-card"><div class="l">年間予想配当（税引前）</div><div class="v" id="k-div-gross">¥0</div></div>
  <div class="kpi-card"><div class="l">年間予想配当（税引後 約20.315%）</div><div class="v" id="k-div-net">¥0</div></div>
  <div class="kpi-card"><div class="l">加重平均利回り（時価 / 簿価YOC）</div><div class="v" id="k-yld">0.00%</div></div>
</div>
<div class="card">
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
    <input type="text" id="p-code" placeholder="コード (例: 8058)" style="width:120px;">
    <input type="number" id="p-shares" placeholder="株数 (例: 100)" value="100" style="width:110px;">
    <input type="number" id="p-cost" placeholder="取得単価(円)" style="width:120px;">
    <button class="btn btn-primary" onclick="addRow()">保有銘柄を追加</button>
    <button class="btn" onclick="clearAll()">すべて削除</button>
  </div>
  <div style="overflow-x:auto;">
    <table>
      <thead><tr><th class="left">コード</th><th class="left">銘柄</th><th>株数</th><th>取得単価</th><th>現在値</th><th>評価額</th><th>損益</th><th>1株予想配当</th><th>年間配当(税前)</th><th>YOC</th><th>操作</th></tr></thead>
      <tbody id="pf-body"></tbody>
    </table>
  </div>
</div>
</div>
<script>
const LS_PF = "jp_div_screener_portfolio";
let MAP = {{}};
async function init() {{
  const res = await fetch("ranking.json");
  const data = await res.json();
  (data.items || []).forEach(x => MAP[x.code] = x);
  render();
}}
function getPF() {{ return JSON.parse(localStorage.getItem(LS_PF) || "[]"); }}
function savePF(arr) {{ localStorage.setItem(LS_PF, JSON.stringify(arr)); render(); }}
function addRow() {{
  const code = document.getElementById("p-code").value.trim();
  const shares = Number(document.getElementById("p-shares").value) || 100;
  let cost = Number(document.getElementById("p-cost").value) || 0;
  if (!code) return;
  if (!cost && MAP[code]) cost = MAP[code].price || 0;
  const arr = getPF();
  const idx = arr.findIndex(x => x.code === code);
  if (idx >= 0) {{ arr[idx].shares = shares; arr[idx].avg_cost = cost; }}
  else arr.push({{ code, shares, avg_cost: cost }});
  savePF(arr);
  document.getElementById("p-code").value = "";
  document.getElementById("p-cost").value = "";
}}
function updateCell(i, field, val) {{
  const arr = getPF();
  arr[i][field] = Number(val) || 0;
  savePF(arr);
}}
function removeRow(i) {{
  const arr = getPF(); arr.splice(i, 1); savePF(arr);
}}
function clearAll() {{ if (confirm("ポートフォリオをすべて削除しますか？")) savePF([]); }}
function fmtY(n) {{ return "¥" + Math.round(n).toLocaleString("ja-JP"); }}
function render() {{
  const arr = getPF();
  let totVal = 0, totCost = 0, totDiv = 0;
  const tb = document.getElementById("pf-body");
  if (!arr.length) {{
    tb.innerHTML = "<tr><td colspan='11' style='text-align:center;color:var(--muted);'>保有銘柄がありません。ランキング表の💼または上の入力欄から追加してください。</td></tr>";
  }} else {{
    tb.innerHTML = arr.map((r, i) => {{
      const x = MAP[r.code];
      const cur = x ? (x.price || 0) : r.avg_cost;
      const dps = x && x.fwd_div ? x.fwd_div : (x && x.fwd_yield && cur ? cur * x.fwd_yield / 100 : 0);
      const val = cur * r.shares;
      const cost = r.avg_cost * r.shares;
      const pnl = val - cost;
      const divGross = dps * r.shares;
      const yoc = cost > 0 ? (divGross / cost * 100) : 0;
      totVal += val; totCost += cost; totDiv += divGross;
      return `<tr>
        <td class="left"><a href="reports/${{r.code}}.html"><strong>${{r.code}}</strong></a></td>
        <td class="left">${{x ? x.name : "対象外"}}</td>
        <td><input type="number" value="${{r.shares}}" style="width:76px;" onchange="updateCell(${{i}},'shares',this.value)"></td>
        <td><input type="number" value="${{Math.round(r.avg_cost)}}" style="width:86px;" onchange="updateCell(${{i}},'avg_cost',this.value)"></td>
        <td>${{fmtY(cur)}}</td>
        <td>${{fmtY(val)}}</td>
        <td class="${{pnl>=0?'pos':'neg'}}">${{pnl>=0?'+':''}}${{fmtY(pnl)}}</td>
        <td>¥${{dps.toFixed(1)}}</td>
        <td class="pos">${{fmtY(divGross)}}</td>
        <td>${{yoc.toFixed(2)}}%</td>
        <td><button class="btn" onclick="removeRow(${{i}})">削除</button></td>
      </tr>`;
    }}).join("");
  }}
  const pnlTot = totVal - totCost;
  const divNet = totDiv * (1 - 0.20315);
  const yldCur = totVal > 0 ? (totDiv / totVal * 100) : 0;
  const yldYoc = totCost > 0 ? (totDiv / totCost * 100) : 0;
  document.getElementById("k-val").textContent = fmtY(totVal);
  document.getElementById("k-pnl").innerHTML = `<span class="${{pnlTot>=0?'pos':'neg'}}">${{pnlTot>=0?'+':''}}${{fmtY(pnlTot)}}</span>`;
  document.getElementById("k-div-gross").textContent = fmtY(totDiv);
  document.getElementById("k-div-net").textContent = fmtY(divNet);
  document.getElementById("k-yld").textContent = `${{yldCur.toFixed(2)}}% / ${{yldYoc.toFixed(2)}}%`;
}}
init();
</script>{THEME_SCRIPT}</body></html>"""
    (dist_dir / "portfolio.html").write_text(pf_html, encoding="utf-8")

    # 3. guide.html
    guide_html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>使い方・見方｜日本株 配当株 軍分けランキング</title><style>{BASE_STYLE}</style></head>
<body><div class="wrap">
{_nav_header("📖 使い方・見方（日本株 配当株 軍分けランキング）")}
<div class="card">
  <h2>1. 対象銘柄の抽出条件（スクリーン）</h2>
  <p>東証プライム・スタンダードの内国株式（ETF・REIT・グロース・外国株を除く）を母集団とし、以下の3条件をすべて満たす銘柄を掲載しています。</p>
  <ul>
    <li><strong>直近1年実績配当利回り</strong>: 2.0%以上（補助条件：過去3年平均配当利回り 1.6%以上）</li>
    <li><strong>時価総額</strong>: 300億円以上</li>
    <li><strong>減配の有無</strong>: 直近5年間 減配なし（累進配当・DOE宣言銘柄は例外）</li>
  </ul>
</div>
<div class="card">
  <h2>2. 2つのスコア（各 0〜110点）</h2>
  <ul>
    <li><strong>① 選定スコア（配当株としての質・長期保有適性）</strong>: 業績・財務（自己資本比率含む）・キャッシュフロー・配当の持続力（増配率、連続増配/非減配、配当性向、ROE、総還元利回り）を統合評価。銀行・保険・証券は専用「金融品質」、リース・信販は専用「リース・信販品質」で採点します。</li>
    <li><strong>② 買い時スコア（今の株価の割安度）</strong>: 配当利回りセオリー（自社過去レンジ内位置）、利回り水準＆Chowderルール、PER/PBRバリュエーション、金利スプレッド（対 日本10年国債利回り {jp10y_yield:.2f}%）から算出します。</li>
  </ul>
</div>
<div class="card">
  <h2>3. 軍分け・業種級・業種内偏差値</h2>
  <ul>
    <li><strong>13業種グループ内 軍分け</strong>: 選定スコア上位25%＝1軍 / 続く45%＝2軍 / 残り30%＝3軍（カバレッジ「低」は最高2軍、選定85以上は最低2軍保証、6銘柄未満グループは「―」）。</li>
    <li><strong>業種級 A/B/C</strong>: グループごとの選定スコア中央値で判定。</li>
    <li><strong>業種内偏差値</strong>: 同じ業種の中で選定スコアがどの位置にあるか（50＝平均）を表示・絞り込み専用で併記。</li>
  </ul>
</div>
</div>{THEME_SCRIPT}</body></html>"""
    (dist_dir / "guide.html").write_text(guide_html, encoding="utf-8")

    # 4. terms.html
    terms_html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>利用規約・免責事項｜日本株 配当株 軍分けランキング</title><style>{BASE_STYLE}</style></head>
<body><div class="wrap">
{_nav_header("⚖ 利用規約・免責事項")}
<div class="card">
  <p>本サイトは、JPX（日本取引所グループ）の公開銘柄一覧および Yahoo Finance（yfinance）・stooq 等の公開データを自動収集・機械採点した情報提供ツールです。</p>
  <ul>
    <li>特定の銘柄の売買を推奨・勧誘するものではありません。投資判断は必ずご自身の責任で行ってください。</li>
    <li>無料公開データの特性上、株式分割・記念配当・決算期変更等による誤り・遅延・欠損が含まれる場合があります。最終確認は必ず決算短信・有価証券報告書等の公式IR情報で行ってください。</li>
    <li>ウォッチリストおよびポートフォリオのデータはお使いのブラウザ（LocalStorage）にのみ保存され、外部サーバーへ送信されません。</li>
  </ul>
</div>
</div>{THEME_SCRIPT}</body></html>"""
    (dist_dir / "terms.html").write_text(terms_html, encoding="utf-8")
