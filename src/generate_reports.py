"""日本株 配当株 軍分けランキングの個別銘柄レポート（dist/reports/<CODE>.html）を生成するモジュール。"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _esc(val: Any) -> str:
    return html.escape(str(val)) if val is not None else ""


def _fmt(val: float | int | None, digits: int = 1, suffix: str = "") -> str:
    if val is None:
        return "―"
    return f"{val:,.{digits}f}{suffix}"


def _fmt_yen(val: float | None) -> str:
    if val is None:
        return "―"
    return f"¥{round(val):,}"


def _svg_price_chart(series: list[dict[str, Any]]) -> str:
    if len(series) < 2:
        return "<p style='color:var(--muted);font-size:12px;'>株価推移データなし</p>"
    w, h, pad = 620, 170, 28
    vals = [p["close"] for p in series]
    vmin, vmax = min(vals), max(vals)
    span = vmax - vmin if vmax > vmin else 1.0
    pts = []
    for i, p in enumerate(series):
        x = pad + (w - pad * 2) * (i / (len(series) - 1))
        y = h - pad - (h - pad * 2) * ((p["close"] - vmin) / span)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    start_d, end_d = series[0]["date"], series[-1]["date"]
    return f"""<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:620px;height:auto;background:var(--bg);border-radius:6px;">
  <line x1="{pad}" y1="{pad}" x2="{w-pad}" y2="{pad}" stroke="var(--border)" stroke-dasharray="3 3"/>
  <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="var(--border)"/>
  <polyline fill="none" stroke="var(--accent)" stroke-width="2" points="{poly}"/>
  <text x="{pad}" y="16" font-size="11" fill="var(--muted)">高値 {_fmt_yen(vmax)}</text>
  <text x="{w-pad}" y="16" font-size="11" fill="var(--muted)" text-anchor="end">現在 {_fmt_yen(vals[-1])}</text>
  <text x="{pad}" y="{h-8}" font-size="10" fill="var(--muted)">{start_d}（安値 {_fmt_yen(vmin)}）</text>
  <text x="{w-pad}" y="{h-8}" font-size="10" fill="var(--muted)" text-anchor="end">{end_d}</text>
</svg>"""


def _svg_dividend_chart(annual_series: list[dict[str, Any]]) -> str:
    if not annual_series:
        return "<p style='color:var(--muted);font-size:12px;'>配当推移データなし</p>"
    w, h, pad_x, pad_b, pad_t = 620, 170, 30, 28, 24
    vals = [x["amount"] for x in annual_series]
    vmax = max(vals) if max(vals) > 0 else 1.0
    n = len(annual_series)
    bw = max(14, min(46, int((w - pad_x * 2) / max(n, 1) * 0.65)))
    step = (w - pad_x * 2) / max(n, 1)
    bars = []
    for i, row in enumerate(annual_series):
        cx = pad_x + step * i + step / 2
        bh = (h - pad_b - pad_t) * (row["amount"] / vmax)
        y = h - pad_b - bh
        bars.append(
            f'<rect x="{cx - bw/2:.1f}" y="{y:.1f}" width="{bw}" height="{bh:.1f}" rx="3" fill="var(--good)" opacity="0.85"/>'
            f'<text x="{cx:.1f}" y="{y - 4:.1f}" font-size="10" fill="var(--text)" text-anchor="middle">¥{row["amount"]:.0f}</text>'
            f'<text x="{cx:.1f}" y="{h - 10}" font-size="10" fill="var(--muted)" text-anchor="middle">{row["year"]}</text>'
        )
    return f"""<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:620px;height:auto;background:var(--bg);border-radius:6px;">
  <line x1="{pad_x}" y1="{h-pad_b}" x2="{w-pad_x}" y2="{h-pad_b}" stroke="var(--border)"/>
  {"".join(bars)}
</svg>"""


def _render_report(item: dict[str, Any], jp10y_yield: float) -> str:
    code = item["code"]
    name = item["name"]
    sc = item["scoring"]
    m = sc["metrics"]
    p = item["price"]
    div = item.get("dividend", {})
    prof = item.get("profile", {})
    val = item.get("valuation", {})

    warns = sc.get("warnings", [])
    warn_box = ""
    if warns:
        li = "".join(f"<li>{_esc(w)}</li>" for w in warns)
        warn_box = f"""<div class="warn-box"><strong>⚠ 機械的注意ポイント（採点には不使用）</strong><ul>{li}</ul></div>"""

    model_note = ""
    if sc["model"] in ("bank", "ins_sec"):
        model_note = "<div class='info-box'>※ 銀行・保険・証券モデル: 業績・財務・CFの代わりに専用「金融品質」＋「配当の持続力」で選定スコアを算出しています。貸倒費用・自己資本比率規制値等は決算短信でご確認ください。</div>"
    elif sc["model"] == "lease":
        model_note = "<div class='info-box'>※ リース・信販モデル: 営業CFが構造的にマイナスになりやすいためCFは参考表示とし、専用「リース・信販品質（ROA・総資産成長率・利払い余力）」で採点しています。</div>"

    dev_text = f"業種内偏差値 {sc['sector_dev']:.1f}（{sc['sector_dev_info']}）" if sc.get("sector_dev") is not None else "業種内偏差値 ―"
    payout_disp = "赤字" if m.get("is_loss_latest") else _fmt(m.get("payout_ratio"), 1, "%")

    eh_rows = ""
    for e in item.get("earnings_history", []):
        sp = f"{e['surprise_pct']*100:+.1f}%" if e.get("surprise_pct") is not None else "―"
        eh_rows += f"<tr><td>{_esc(e['date'])}</td><td>{_fmt(e.get('eps_actual'),1,'円')}</td><td>{_fmt(e.get('eps_estimate'),1,'円')}</td><td>{sp}</td></tr>"
    if not eh_rows:
        eh_rows = "<tr><td colspan='4' style='text-align:center;color:var(--muted);'>直近決算サプライズデータなし</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(code)} {_esc(name)}｜日本株 配当株レポート</title>
<style>
:root {{
  --bg: #f6f8fb; --surface: #ffffff; --border: #dfe5ef; --text: #1b2432; --muted: #5f6c80;
  --accent: #1d5fd6; --accent-soft: #eaf1ff; --good: #137333; --warn: #b06000; --bad: #c5221f;
}}
body.dark {{
  --bg: #0f141d; --surface: #18202c; --border: #2a3547; --text: #e8eef7; --muted: #9aa7bd;
  --accent: #5e9bff; --accent-soft: #1d2c44; --good: #6ee79c; --warn: #fbbf24; --bad: #f87171;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.6; }}
a {{ color: var(--accent); text-decoration: none; }}
.wrap {{ max-width: 1020px; margin: 0 auto; padding: 16px 16px 60px; }}
.top-nav {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; font-size: 13px; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 14px; }}
h1 {{ margin: 0 0 6px; font-size: 22px; }}
.meta {{ color: var(--muted); font-size: 12.5px; }}
.score-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 12px; }}
.score-box {{ background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }}
.score-val {{ font-size: 30px; font-weight: 800; color: var(--accent); }}
.summary-line {{ margin-top: 10px; padding: 10px 12px; background: var(--accent-soft); border-radius: 6px; font-weight: 600; font-size: 13.5px; }}
.warn-box {{ background: #fff7ed; border: 1px solid #fdba74; color: #9a3412; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px; }}
body.dark .warn-box {{ background: #3b1f0b; border-color: #9a3412; color: #fed7aa; }}
.info-box {{ background: var(--accent-soft); border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; font-size: 12.5px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 7px 10px; border-bottom: 1px solid var(--border); text-align: left; }}
th {{ color: var(--muted); font-weight: 600; width: 38%; }}
.chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; border-left: 4px solid var(--accent); padding-left: 8px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="top-nav">
    <a href="../index.html">← ランキング一覧へ戻る</a>
    <a href="../watchlist.html">☆ ウォッチリスト</a>
    <a href="../portfolio.html">💼 ポートフォリオ</a>
    <a href="../guide.html">使い方・見方</a>
  </div>

  <div class="card">
    <h1>{_esc(code)} {_esc(name)} <span style="font-size:14px;color:var(--muted);">({sc['tier']} / 全体{sc['overall_rank']}位)</span></h1>
    <div class="meta">
      業種: {_esc(item.get('sector_group'))}（{_esc(item.get('sector33'))}） ｜ 市場: {_esc(item.get('market'))} ｜
      終値: <strong>{_fmt_yen(p.get('current'))}</strong>（{_esc(p.get('date'))}） ｜
      時価総額: <strong>{_fmt(m.get('market_cap_oku'), 0, '億円')}</strong>
      {" ｜ <strong>累進配当/DOE宣言</strong>" if item.get("is_progressive") else ""}
    </div>

    <div class="score-grid">
      <div class="score-box">
        <div style="font-size:12px;color:var(--muted);">① 銘柄選定スコア（0〜110）</div>
        <div class="score-val">{sc['selection_score']:.1f}</div>
        <div style="font-size:12.5px;font-weight:600;">{_esc(sc['selection_label'])}</div>
        <div style="font-size:11.5px;color:var(--muted);margin-top:4px;">{_esc(dev_text)} ／ カバレッジ: {sc['coverage']}（{sc['coverage_pct']:.0f}%）</div>
      </div>
      <div class="score-box">
        <div style="font-size:12px;color:var(--muted);">② 買い時スコア（0〜110）</div>
        <div class="score-val">{sc['timing_score']:.1f}</div>
        <div style="font-size:12.5px;font-weight:600;">{_esc(sc['timing_label'])}</div>
        <div style="font-size:11.5px;color:var(--muted);margin-top:4px;">予想配当利回り: {_fmt(m.get('fwd_yield'), 2, '%')} ／ Chowder: {_fmt(m.get('chowder'), 1, '%')}</div>
      </div>
    </div>

    <div class="summary-line">
      → 選定は「{_esc(sc['selection_label'])}」、買い時は「{_esc(sc['timing_label'])}」
    </div>
  </div>

  {warn_box}
  {model_note}

  <div class="card">
    <h2>📈 株価推移 ＆ 1株配当の長期推移</h2>
    <div class="chart-grid">
      <div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">週次株価推移（最大5年）</div>
        {_svg_price_chart(p.get('price_series_weekly', []))}
      </div>
      <div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">年間1株配当推移（円）</div>
        {_svg_dividend_chart(div.get('annual_series', []))}
      </div>
    </div>
  </div>

  <div class="card">
    <h2>① 銘柄選定スコアの内訳（配当株としての質）</h2>
    <table>
      <tr><th>業績スコア / 売上CAGR / EPS CAGR / 営業利益率</th><td>{_fmt(sc.get('perf_score'),1,'点')} ｜ 売上 {_fmt(m.get('rev_cagr'),1,'%')} ｜ EPS {_fmt(m.get('eps_cagr'),1,'%')} ｜ 営業利益率 {_fmt(m.get('op_margin'),1,'%')}</td></tr>
      <tr><th>財務スコア / 自己資本比率 / D/E / ネットD/E</th><td>{_fmt(sc.get('fin_score'),1,'点')} ｜ 自己資本比率 {_fmt(m.get('equity_ratio'),1,'%')} ｜ D/E {_fmt(m.get('de_ratio'),2,'倍')} ｜ Net D/E {_fmt(m.get('net_de'),2,'倍')}</td></tr>
      <tr><th>CFスコア / 営業CF / フリーCF / FCF配当性向</th><td>{_fmt(sc.get('cf_score'),1,'点')} ｜ 営業CF {"黒字" if m.get('ocf_positive') else "赤字/不明"} ｜ FCF {"黒字" if m.get('fcf_positive') else "赤字/不明"} ｜ FCF配当性向 {_fmt(m.get('fcf_payout'),1,'%')}</td></tr>
      <tr><th>配当の持続力スコア / 5年増配率 / 連続増配 / 非減配</th><td>{_fmt(sc.get('div_sust_score'),1,'点')} ｜ 増配率 {_fmt(m.get('div_cagr'),1,'%')} ｜ 連続増配 {m.get('consec_increase',0)}年 ｜ 連続非減配 {m.get('consec_no_cut',0)}年</td></tr>
      <tr><th>配当性向（純利益ベース） / ROE / 総還元利回り</th><td>配当性向 {payout_disp} ｜ ROE {_fmt(m.get('roe'),1,'%')} ｜ 総還元利回り {_fmt(m.get('total_return_yield'),2,'%')}（自社株買い {_fmt(m.get('buyback_yield'),2,'%')}）</td></tr>
      <tr><th>参考（採点外表示）：ROA / 利払い余裕度(ICR)</th><td>ROA {_fmt(m.get('roa'),1,'%')} ｜ ICR {_fmt(m.get('icr'),1,'倍')}</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>② 買い時スコアの内訳（割安度・利回り水準）</h2>
    <table>
      <tr><th>配当利回りセオリー（過去レンジ内位置）</th><td>{_fmt(m.get('div_yield_range_pos'),1,'%')}（高いほど過去比で高利回り・割安）</td></tr>
      <tr><th>予想配当利回り / 実績利回り / 3年平均利回り</th><td>予想 {_fmt(m.get('fwd_yield'),2,'%')}（年間 {_fmt(div.get('fwd_div'),1,'円')}） ｜ 実績 {_fmt(m.get('ttm_yield'),2,'%')} ｜ 3年平均 {_fmt(m.get('avg_yield_3y'),2,'%')}</td></tr>
      <tr><th>Chowderルール（予想利回り＋5年増配率）</th><td>{_fmt(m.get('chowder'),1,'%')}（12%以上で良好）</td></tr>
      <tr><th>PER（実績・対業種中央値・過去レンジ位置）</th><td>{_fmt(m.get('trailing_pe'),1,'倍')}（業種中央値 {_fmt(m.get('sector_med_pe'),1,'倍')}・対業種 {_fmt(m.get('pe_rel_sector'),2,'倍')}・過去レンジ {_fmt(m.get('per_range_pos'),1,'%')}）</td></tr>
      <tr><th>PBR（実績・対業種中央値）</th><td>{_fmt(m.get('pbr'),2,'倍')}（業種中央値 {_fmt(m.get('sector_med_pbr'),2,'倍')}・対業種 {_fmt(m.get('pbr_rel_sector'),2,'倍')}）</td></tr>
      <tr><th>金利スプレッド（予想利回り − 日本10年国債 {jp10y_yield:.2f}%）</th><td>{_fmt(m.get('yield_spread'),2,'%')}</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>📊 直近決算・アナリスト予想・テクニカル</h2>
    <p style="font-size:13px;margin:0 0 8px;">
      アナリスト目標株価: <strong>{_fmt_yen(val.get('target_mean_price'))}</strong> ／
      レーティング: <strong>{_esc(val.get('recommendation') or '―')}</strong>（対象 {val.get('analyst_count') or '―'}名） ／
      RSI(14): <strong>{_fmt(p.get('rsi14'),1)}</strong>
    </p>
    <table>
      <thead><tr><th>決算日</th><th>実績EPS</th><th>予想EPS</th><th>サプライズ</th></tr></thead>
      <tbody>{eh_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>🏢 企業概要</h2>
    <p style="font-size:12.5px;color:var(--muted);margin:0 0 6px;">
      所在地: {_esc(prof.get('city') or '―')} ／ 従業員数: {_fmt(prof.get('employees'), 0, '名') if prof.get('employees') else '―'}
    </p>
    <p style="font-size:13px;margin:0;">{_esc(prof.get('summary_en') or '企業概要データなし')}</p>
  </div>
</div>
<script>
try {{
  const t = JSON.parse(localStorage.getItem("jp_div_screener_theme") || "null");
  if (t && t.dark) document.body.classList.add("dark");
}} catch(e) {{}}
</script>
</body>
</html>
"""


def generate_reports(items: list[dict[str, Any]], dist_dir: Path, jp10y_yield: float = 1.50) -> int:
    rep_dir = dist_dir / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    for it in items:
        html_str = _render_report(it, jp10y_yield=jp10y_yield)
        (rep_dir / f"{it['code']}.html").write_text(html_str, encoding="utf-8")
    return len(items)
