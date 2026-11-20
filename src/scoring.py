"""日本株 配当株 軍分けランキングの選定スコア・買い時スコア・業種内偏差値・軍分け・業種級を算出するモジュール。"""

from __future__ import annotations

import math
from statistics import mean, median, pstdev
from typing import Any

from src.fetch_jpx import GROUP_ORDER

RATE_SENSITIVE_GROUPS = {
    "資源・エネルギー",
    "建設・不動産",
    "インフラ・運輸",
    "情報通信・サービス",
    "銀行",
    "保険・証券",
    "リース・信販・その他金融",
}


def _piecewise(val: float | None, points: list[tuple[float, float]]) -> float | None:
    if val is None or math.isnan(val) or math.isinf(val):
        return None
    if val <= points[0][0]:
        return points[0][1]
    if val >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= val <= x1:
            if x1 == x0:
                return y1
            return y0 + (val - x0) / (x1 - x0) * (y1 - y0)
    return None


def _avg(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def _weighted_avg(pairs: list[tuple[float | None, float]]) -> float | None:
    num, den = 0.0, 0.0
    for val, w in pairs:
        if val is not None:
            num += val * w
            den += w
    return num / den if den > 0 else None


def _calc_cagr(series: list[dict[str, Any]]) -> float | None:
    if len(series) < 2:
        return None
    latest, oldest = series[0]["value"], series[-1]["value"]
    years = len(series) - 1
    if oldest is None or latest is None or oldest <= 0 or latest <= 0:
        if oldest and oldest != 0 and latest is not None:
            pct = (latest - oldest) / abs(oldest) * 100.0 / years
            return round(max(-50.0, min(50.0, pct)), 2)
        return None
    cagr = ((latest / oldest) ** (1.0 / years) - 1.0) * 100.0
    return round(max(-80.0, min(150.0, cagr)), 2)


def classify_model(stock: dict[str, Any]) -> str:
    """業種グループから採点モデル（general / bank / ins_sec / lease）を判定する。"""
    grp = stock.get("sector_group", "")
    if grp == "銀行":
        return "bank"
    if grp == "保険・証券":
        return "ins_sec"
    if grp == "リース・信販・その他金融":
        return "lease"
    return "general"


def _compute_raw_metrics(stock: dict[str, Any], jp10y_yield: float) -> dict[str, Any]:
    fin = stock.get("financials", {})
    q = stock.get("quarterly", {})
    bs = stock.get("balance_sheet", {})
    cf = stock.get("cashflow", {})
    val = stock.get("valuation", {})
    div = stock.get("dividend", {})
    price_info = stock.get("price", {})

    model = classify_model(stock)
    is_fin = model in ("bank", "ins_sec", "lease")
    mkt_cap = price_info.get("market_cap")
    cur_price = price_info.get("current")

    rev_s = fin.get("revenue", [])
    op_s = fin.get("operating_income", [])
    pretax_s = fin.get("pretax_income", [])
    ni_s = fin.get("net_income", [])
    eps_s = fin.get("eps", [])
    int_s = fin.get("interest_expense", [])

    debt_s = bs.get("total_debt", [])
    cash_s = bs.get("cash", [])
    eq_s = bs.get("equity", [])
    assets_s = bs.get("total_assets", [])

    ocf_s = cf.get("operating_cf", [])
    capex_s = cf.get("capex", [])
    fcf_s = cf.get("free_cf", [])
    div_paid_s = cf.get("dividends_paid", [])
    buyback_s = cf.get("buybacks", [])

    # --- 業績 ---
    rev_cagr = _calc_cagr(rev_s)
    eps_cagr = _calc_cagr(eps_s) or _calc_cagr(ni_s)
    op_margin = (
        round(op_s[0]["value"] / rev_s[0]["value"] * 100.0, 2)
        if (rev_s and op_s and rev_s[0]["value"] and rev_s[0]["value"] > 0)
        else None
    )

    profit_series = [x["value"] for x in (op_s or ni_s) if x.get("value") is not None]
    profit_stability = None
    if len(profit_series) >= 2:
        pos_ratio = sum(1 for v in profit_series if v > 0) / len(profit_series)
        mean_abs = sum(abs(v) for v in profit_series) / len(profit_series)
        if mean_abs > 0:
            diffs = [abs(profit_series[i] - profit_series[i + 1]) / mean_abs for i in range(len(profit_series) - 1)]
            vol = sum(diffs) / len(diffs)
            profit_stability = round(max(0.0, min(1.0, pos_ratio * 0.8 + max(0.0, 0.2 - vol * 0.35))), 2)

    # 直近四半期急減速チェック
    q_rev = q.get("revenue", [])
    q_op = q.get("operating_income", [])
    q_ni = q.get("net_income", [])
    q_rev_yoy = (
        round((q_rev[0]["value"] / q_rev[4]["value"] - 1.0) * 100.0, 2)
        if (len(q_rev) >= 5 and q_rev[4]["value"] and q_rev[4]["value"] > 0)
        else None
    )
    pq = q_op if len(q_op) >= 5 else q_ni
    q_profit_yoy = (
        round((pq[0]["value"] - pq[4]["value"]) / abs(pq[4]["value"]) * 100.0, 2)
        if (len(pq) >= 5 and pq[4]["value"] and abs(pq[4]["value"]) > 0)
        else None
    )
    rapid_decel = bool(q_rev_yoy is not None and q_profit_yoy is not None and q_rev_yoy < -5.0 and q_profit_yoy < -15.0)

    # --- 財務 ---
    debt_v = debt_s[0]["value"] if debt_s else None
    cash_v = cash_s[0]["value"] if cash_s else 0.0
    eq_v = eq_s[0]["value"] if eq_s else None
    assets_v = assets_s[0]["value"] if assets_s else None
    ocf_v = ocf_s[0]["value"] if ocf_s else None
    capex_v = capex_s[0]["value"] if capex_s else None
    fcf_v = fcf_s[0]["value"] if fcf_s else (ocf_v - abs(capex_v) if (ocf_v is not None and capex_v is not None) else None)
    ni_v = ni_s[0]["value"] if ni_s else None
    pretax_v = pretax_s[0]["value"] if pretax_s else None
    int_v = abs(int_s[0]["value"]) if (int_s and int_s[0]["value"]) else None

    equity_ratio = round(eq_v / assets_v * 100.0, 1) if (eq_v is not None and assets_v and assets_v > 0) else None
    de_ratio = round(debt_v / eq_v, 2) if (debt_v is not None and eq_v and eq_v > 0) else None
    net_de = round((debt_v - (cash_v or 0.0)) / eq_v, 2) if (debt_v is not None and eq_v and eq_v > 0) else None
    debt_to_ocf = round(debt_v / ocf_v, 2) if (debt_v is not None and ocf_v and ocf_v > 0) else None
    icr = round((pretax_v + int_v) / int_v, 2) if (pretax_v is not None and int_v and int_v > 0) else None

    # --- CF ---
    ocf_positive = bool(ocf_v is not None and ocf_v > 0)
    fcf_positive = bool(fcf_v is not None and fcf_v > 0)
    div_paid_v = abs(div_paid_s[0]["value"]) if (div_paid_s and div_paid_s[0]["value"]) else None
    fcf_payout = None
    if div_paid_v is not None and fcf_v is not None:
        fcf_payout = round(div_paid_v / fcf_v * 100.0, 1) if fcf_v > 0 else 150.0

    # --- ROE / ROA ---
    roe = (
        round(ni_v / eq_v * 100.0, 1)
        if (ni_v is not None and eq_v and eq_v > 0)
        else (round(val["roe_info"] * 100.0, 1) if val.get("roe_info") is not None else None)
    )
    roa = (
        round(ni_v / assets_v * 100.0, 1)
        if (ni_v is not None and assets_v and assets_v > 0)
        else (round(val["roa_info"] * 100.0, 1) if val.get("roa_info") is not None else None)
    )

    # --- 配当の持続力 ---
    fwd_yield = div.get("fwd_yield")
    ttm_yield = div.get("ttm_yield")
    div_cagr = div.get("div_cagr_5y")
    consec_inc = div.get("consec_increase", 0)
    consec_nocut = div.get("consec_no_cut", 0)
    div_range_pos = div.get("div_yield_range_pos")

    # 配当性向（純利益ベース）
    payout_ratio = None
    is_loss_latest = bool(ni_v is not None and ni_v <= 0)
    if not is_loss_latest:
        if div_paid_v is not None and ni_v and ni_v > 0:
            pr = div_paid_v / ni_v * 100.0
            if 0 <= pr <= 300:
                payout_ratio = round(pr, 1)
        if payout_ratio is None and val.get("payout_ratio_info") is not None:
            pr = val["payout_ratio_info"] * 100.0
            if 0 <= pr <= 300:
                payout_ratio = round(pr, 1)

    # 総還元利回り（配当利回り＋自社株買い利回り）
    buyback_v = abs(buyback_s[0]["value"]) if (buyback_s and buyback_s[0]["value"]) else 0.0
    buyback_yield = round(buyback_v / mkt_cap * 100.0, 2) if (mkt_cap and mkt_cap > 0 and buyback_v > 0) else 0.0
    total_return_yield = round((fwd_yield or ttm_yield or 0.0) + buyback_yield, 2) if (fwd_yield or ttm_yield) is not None else None

    # Chowderルール（予想配当利回り + 5年増配率）
    chowder = round(fwd_yield + div_cagr, 2) if (fwd_yield is not None and div_cagr is not None) else None

    # 金利スプレッド（予想配当利回り - 日本10年国債利回り）
    yield_spread = round(fwd_yield - jp10y_yield, 2) if fwd_yield is not None else None

    # --- バリュエーション ---
    trailing_pe = val.get("trailing_pe")
    if trailing_pe is not None and (trailing_pe <= 0 or trailing_pe > 200):
        trailing_pe = None
    pbr = val.get("price_to_book")
    if pbr is not None and (pbr <= 0 or pbr > 100):
        pbr = None

    per_range_pos = None
    yearly_prices = price_info.get("yearly_prices", {})
    if trailing_pe is not None and eps_s and yearly_prices:
        hist_pers = []
        for row in eps_s:
            yr, e = row["date"][:4], row["value"]
            p_info = yearly_prices.get(yr)
            if e and e > 0 and p_info and p_info.get("avg", 0) > 0:
                pe_yr = p_info["avg"] / e
                if 2.0 <= pe_yr <= 120.0:
                    hist_pers.append(pe_yr)
        if len(hist_pers) >= 2:
            p_min, p_max = min(hist_pers), max(hist_pers)
            per_range_pos = (
                round(max(0.0, min(100.0, (p_max - trailing_pe) / (p_max - p_min) * 100.0)), 1)
                if p_max > p_min
                else 50.0
            )

    # --- 各グループの採点（0〜110点） ---
    # 1. 業績
    s_rev = _piecewise(rev_cagr, [(-6, 20), (0, 55), (3, 78), (8, 96), (15, 110)])
    s_eps = _piecewise(eps_cagr, [(-8, 15), (0, 55), (5, 80), (12, 98), (20, 110)])
    s_margin = _piecewise(op_margin, [(0, 15), (4, 52), (10, 82), (18, 98), (28, 110)])
    s_stab = _piecewise(profit_stability, [(0.4, 20), (0.65, 58), (0.88, 90), (1.0, 110)])
    perf_score = _avg([s_rev, s_eps, s_margin, s_stab])
    if perf_score is not None and rapid_decel:
        perf_score *= 0.80

    # 2. 財務（日本株向け：自己資本比率含む）
    s_eq = _piecewise(equity_ratio, [(10, 15), (25, 52), (40, 82), (60, 98), (75, 110)])
    s_de = _piecewise(de_ratio, [(0.0, 110), (0.3, 98), (0.8, 80), (1.8, 52), (3.5, 20)])
    s_nde = _piecewise(net_de, [(-0.3, 110), (0.0, 100), (0.5, 80), (1.5, 52), (3.0, 20)])
    s_docf = _piecewise(debt_to_ocf, [(0.0, 110), (1.5, 95), (3.5, 76), (7.0, 48), (12.0, 20)])
    s_icr = _piecewise(icr, [(1.0, 20), (3.0, 55), (8.0, 84), (20.0, 100), (40.0, 110)])
    fin_score = _avg([s_eq, s_de, s_nde, s_docf, s_icr])

    # 3. CF
    s_ocf = 95.0 if ocf_positive else (25.0 if ocf_v is not None else None)
    s_fcf = 95.0 if fcf_positive else (25.0 if fcf_v is not None else None)
    s_fcf_p = _piecewise(fcf_payout, [(0, 105), (40, 98), (70, 82), (100, 52), (140, 20)])
    cf_score = _avg([s_ocf, s_fcf, s_fcf_p])

    # 4. 配当の持続力
    s_dcagr = _piecewise(div_cagr, [(-5, 15), (0, 52), (3, 80), (8, 98), (15, 110)])
    s_cinc = _piecewise(float(consec_inc), [(0, 35), (3, 68), (5, 82), (10, 98), (15, 110)])
    s_cnocut = _piecewise(float(consec_nocut), [(0, 20), (5, 65), (10, 84), (15, 100), (20, 110)])
    s_payout = _piecewise(payout_ratio, [(15, 92), (35, 105), (50, 90), (75, 58), (100, 25), (130, 10)])
    s_roe = _piecewise(roe, [(0, 15), (6, 55), (10, 84), (15, 98), (22, 110)])
    s_tr = _piecewise(total_return_yield, [(1.5, 45), (3.0, 74), (4.5, 92), (6.5, 105), (8.5, 110)])
    div_sust_score = _avg([s_dcagr, s_cinc, s_cnocut, s_payout, s_roe, s_tr])

    # 銀行・保険証券向け「金融品質」
    fin_quality_score = _avg([s_roe, s_rev, s_eps, s_stab])

    # リース・信販向け「リース品質」
    assets_cagr = _calc_cagr(assets_s)
    is_funding_type = equity_ratio is not None and equity_ratio < 30.0
    s_lease_roa = (
        _piecewise(roa, [(0.0, 20), (0.5, 55), (1.0, 84), (1.8, 100), (2.8, 110)])
        if is_funding_type
        else _piecewise(roa, [(0.0, 20), (2.0, 55), (5.0, 84), (8.0, 100), (12.0, 110)])
    )
    s_assets_g = _piecewise(assets_cagr, [(-5, 25), (0, 55), (4, 82), (10, 100), (18, 110)]) if is_funding_type else None
    lease_quality_score = _avg([s_lease_roa, s_assets_g, s_icr])

    # --- 選定スコア合成 ---
    if model in ("bank", "ins_sec"):
        selection_score = _weighted_avg([(fin_quality_score, 0.55), (div_sust_score, 0.45)])
        comp_present = sum(1 for x in [s_roe, s_rev, s_eps, s_stab, s_dcagr, s_cinc, s_cnocut, s_payout, s_tr] if x is not None)
        comp_total = 9
    elif model == "lease":
        selection_score = _weighted_avg([(perf_score, 0.22), (fin_score, 0.20), (lease_quality_score, 0.18), (div_sust_score, 0.40)])
        comp_present = sum(
            1
            for x in [s_rev, s_eps, s_margin, s_stab, s_eq, s_de, s_lease_roa, s_icr, s_dcagr, s_cinc, s_cnocut, s_payout, s_roe]
            if x is not None
        )
        comp_total = 13
    else:
        selection_score = _weighted_avg([(perf_score, 0.22), (fin_score, 0.20), (cf_score, 0.18), (div_sust_score, 0.40)])
        comp_present = sum(
            1
            for x in [s_rev, s_eps, s_margin, s_stab, s_eq, s_de, s_nde, s_ocf, s_fcf, s_fcf_p, s_dcagr, s_cinc, s_cnocut, s_payout, s_roe]
            if x is not None
        )
        comp_total = 15

    selection_score = round(selection_score, 1) if selection_score is not None else 50.0
    cov_pct = round(comp_present / comp_total * 100.0, 1) if comp_total > 0 else 0.0
    coverage = "高" if cov_pct >= 85.0 else ("中" if cov_pct >= 65.0 else "低")

    # ⚠ 注意マーク（採点には一切不使用・表示専用）
    warnings: list[str] = []
    if roe is not None and roa is not None and roe >= 10.0 and roa < 3.0 and not is_fin:
        warnings.append("ROE高(10%以上)に対しROA低(3%未満): レバレッジ依存の可能性")
    if len(ni_s) >= 3 and all((x.get("value") or 0) < 0 for x in ni_s[:3]):
        warnings.append("純損失が3期連続")
    if eq_v is not None and eq_v < 0:
        warnings.append("債務超過")
    if not is_fin and len(ocf_s) >= 2 and all((x.get("value") or 0) < 0 for x in ocf_s[:2]):
        warnings.append("営業CFが2期連続マイナス")
    if not is_fin and equity_ratio is not None and equity_ratio < 10.0:
        warnings.append("自己資本比率が10%未満")
    if not is_fin and fcf_payout is not None and fcf_payout > 100.0:
        warnings.append("FCF配当性向が100%超")
    if payout_ratio is not None and payout_ratio > 100.0:
        warnings.append("配当性向が100%超")
    if is_loss_latest:
        warnings.append("直近決算が純損失（赤字）")
    if pbr is not None and pbr < 1.0 and roe is not None and roe < 5.0:
        warnings.append("PBR1倍割れかつROE5%未満（バリュートラップ注意）")

    return {
        "model": model,
        "is_financial": is_fin,
        "selection_score": selection_score,
        "perf_score": round(perf_score, 1) if perf_score is not None else None,
        "fin_score": round(fin_score, 1) if fin_score is not None else None,
        "cf_score": round(cf_score, 1) if cf_score is not None else None,
        "div_sust_score": round(div_sust_score, 1) if div_sust_score is not None else None,
        "fin_quality_score": round(fin_quality_score, 1) if fin_quality_score is not None else None,
        "lease_quality_score": round(lease_quality_score, 1) if lease_quality_score is not None else None,
        "coverage": coverage,
        "coverage_pct": cov_pct,
        "warnings": warnings,
        "metrics": {
            "rev_cagr": rev_cagr,
            "eps_cagr": eps_cagr,
            "op_margin": op_margin,
            "profit_stability": profit_stability,
            "q_rev_yoy": q_rev_yoy,
            "q_profit_yoy": q_profit_yoy,
            "rapid_decel": rapid_decel,
            "equity_ratio": equity_ratio,
            "de_ratio": de_ratio,
            "net_de": net_de,
            "debt_to_ocf": debt_to_ocf,
            "icr": icr,
            "ocf_positive": ocf_positive,
            "fcf_positive": fcf_positive,
            "fcf_payout": fcf_payout,
            "roe": roe,
            "roa": roa,
            "fwd_yield": fwd_yield,
            "ttm_yield": ttm_yield,
            "avg_yield_3y": div.get("avg_yield_3y"),
            "div_cagr": div_cagr,
            "consec_increase": consec_inc,
            "consec_no_cut": consec_nocut,
            "payout_ratio": payout_ratio,
            "is_loss_latest": is_loss_latest,
            "total_return_yield": total_return_yield,
            "buyback_yield": buyback_yield,
            "chowder": chowder,
            "yield_spread": yield_spread,
            "div_yield_range_pos": div_range_pos,
            "trailing_pe": trailing_pe,
            "pbr": pbr,
            "per_range_pos": per_range_pos,
            "market_cap_oku": round(mkt_cap / 1e8, 0) if mkt_cap else None,
            "cur_price": cur_price,
        },
    }


def _selection_label(score: float) -> str:
    if score >= 85.0:
        return "選定スコア上位（質・持続力とも高水準）"
    if score >= 68.0:
        return "選定スコア中位（標準以上の質）"
    if score >= 55.0:
        return "選定スコア下位（やや慎重確認）"
    return "基準未達（質・持続力に課題）"


def _timing_label(score: float) -> str:
    if score >= 98.0:
        return "割安水準"
    if score >= 82.0:
        return "妥当水準"
    if score >= 64.0:
        return "やや割高"
    return "割高"


def score_all_stocks(
    stocks: list[dict[str, Any]],
    jp10y_yield: float = 1.50,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """全銘柄の選定・買い時スコア、業種内偏差値、軍分け、業種級を一括算出する。"""
    enriched: list[dict[str, Any]] = []
    for s in stocks:
        res = _compute_raw_metrics(s, jp10y_yield=jp10y_yield)
        item = dict(s)
        item["scoring"] = res
        enriched.append(item)

    # 1. 業種グループ別の PER / PBR 中央値を算出
    grp_pers: dict[str, list[float]] = {}
    grp_pbrs: dict[str, list[float]] = {}
    for it in enriched:
        grp = it.get("sector_group", "情報通信・サービス")
        m = it["scoring"]["metrics"]
        if m["trailing_pe"] is not None:
            grp_pers.setdefault(grp, []).append(m["trailing_pe"])
        if m["pbr"] is not None:
            grp_pbrs.setdefault(grp, []).append(m["pbr"])

    all_pers = [v for vs in grp_pers.values() for v in vs]
    all_pbrs = [v for vs in grp_pbrs.values() for v in vs]
    global_pe = median(all_pers) if all_pers else 14.0
    global_pbr = median(all_pbrs) if all_pbrs else 1.2

    # 2. 買い時スコア算出（0〜110点）
    for it in enriched:
        grp = it.get("sector_group", "情報通信・サービス")
        m = it["scoring"]["metrics"]

        med_pe = median(grp_pers[grp]) if len(grp_pers.get(grp, [])) >= 3 else global_pe
        med_pbr = median(grp_pbrs[grp]) if len(grp_pbrs.get(grp, [])) >= 3 else global_pbr

        pe_rel = round(m["trailing_pe"] / med_pe, 2) if (m["trailing_pe"] is not None and med_pe > 0) else None
        pbr_rel = round(m["pbr"] / med_pbr, 2) if (m["pbr"] is not None and med_pbr > 0) else None
        m["pe_rel_sector"] = pe_rel
        m["pbr_rel_sector"] = pbr_rel
        m["sector_med_pe"] = round(med_pe, 1)
        m["sector_med_pbr"] = round(med_pbr, 2)

        # ① 配当利回りセオリー（自社過去レンジ内位置 %）
        s_div_theory = _piecewise(m["div_yield_range_pos"], [(0, 30), (20, 58), (50, 82), (75, 98), (100, 110)])

        # ② 利回り水準とChowder
        s_yield_lvl = _piecewise(m["fwd_yield"], [(1.5, 35), (2.5, 68), (3.5, 88), (4.5, 102), (6.0, 110)])
        s_chowder = _piecewise(m["chowder"], [(4, 30), (8, 65), (12, 90), (16, 104), (20, 110)])
        s_yield_grp = _avg([s_yield_lvl, s_chowder])

        # ③ 株価バリュエーション
        s_pe_rel = _piecewise(pe_rel, [(0.55, 110), (0.80, 98), (0.95, 86), (1.15, 68), (1.45, 42), (1.90, 20)])
        s_pbr_rel = _piecewise(pbr_rel, [(0.55, 110), (0.85, 96), (1.05, 82), (1.35, 62), (1.80, 38), (2.50, 20)])
        s_pe_rng = _piecewise(m["per_range_pos"], [(0, 30), (20, 58), (50, 82), (75, 98), (100, 110)])
        s_val_grp = _avg([s_pe_rel, s_pbr_rel, s_pe_rng])

        # ④ 金利スプレッド（金利敏感業種のみ）
        is_rate_sens = grp in RATE_SENSITIVE_GROUPS
        s_spread = _piecewise(m["yield_spread"], [(0.0, 30), (1.0, 62), (2.0, 86), (3.0, 102), (4.5, 110)]) if is_rate_sens else None

        if is_rate_sens:
            timing = _weighted_avg([(s_div_theory, 0.30), (s_yield_grp, 0.30), (s_val_grp, 0.30), (s_spread, 0.10)])
        else:
            timing = _weighted_avg([(s_div_theory, 0.34), (s_yield_grp, 0.33), (s_val_grp, 0.33)])

        timing_score = round(timing, 1) if timing is not None else 70.0
        it["scoring"]["timing_score"] = timing_score
        it["scoring"]["selection_label"] = _selection_label(it["scoring"]["selection_score"])
        it["scoring"]["timing_label"] = _timing_label(timing_score)
        it["scoring"]["timing_parts"] = {
            "div_theory": round(s_div_theory, 1) if s_div_theory is not None else None,
            "yield_chowder": round(s_yield_grp, 1) if s_yield_grp is not None else None,
            "valuation": round(s_val_grp, 1) if s_val_grp is not None else None,
            "spread": round(s_spread, 1) if s_spread is not None else None,
        }

        # バリュートラップ追加チェック
        if timing_score >= 90.0 and it["scoring"]["selection_score"] < 65.0:
            if not any("バリュートラップ" in w for w in it["scoring"]["warnings"]):
                it["scoring"]["warnings"].append("買い時が高いのに選定スコアが低め（バリュートラップ注意）")

    # 3. 業種内偏差値（東証33業種内で10銘柄以上あれば33業種、未満なら業種グループ内）
    by_sec33: dict[str, list[dict[str, Any]]] = {}
    by_grp: dict[str, list[dict[str, Any]]] = {}
    for it in enriched:
        by_sec33.setdefault(it.get("sector33", ""), []).append(it)
        by_grp.setdefault(it.get("sector_group", "情報通信・サービス"), []).append(it)

    for it in enriched:
        sec33 = it.get("sector33", "")
        grp = it.get("sector_group", "情報通信・サービス")
        pool = by_sec33.get(sec33, [])
        scope_label = sec33
        if len(pool) < 10:
            pool = by_grp.get(grp, [])
            scope_label = f"{grp}（グループ）"
        if len(pool) >= 5:
            vals = [x["scoring"]["selection_score"] for x in pool]
            mu = mean(vals)
            sd = pstdev(vals)
            sc = it["scoring"]["selection_score"]
            dev = round(50.0 + 10.0 * (sc - mu) / sd, 1) if sd > 0.01 else 50.0
            rank_in_pool = sorted(vals, reverse=True).index(sc) + 1
            it["scoring"]["sector_dev"] = dev
            it["scoring"]["sector_dev_info"] = f"{scope_label} {len(pool)}銘柄中 {rank_in_pool}位"
        else:
            it["scoring"]["sector_dev"] = None
            it["scoring"]["sector_dev_info"] = ""

    # 4. 業種グループ別の軍分け & 業種級 A/B/C
    sector_medians: dict[str, float] = {}
    for grp, grp_items in by_grp.items():
        grp_items.sort(key=lambda x: (-x["scoring"]["selection_score"], -x["scoring"]["timing_score"], x["code"]))
        n = len(grp_items)
        sector_medians[grp] = round(median([x["scoring"]["selection_score"] for x in grp_items]), 1)
        if n < 6:
            for x in grp_items:
                x["scoring"]["tier"] = "―"
                x["scoring"]["tier_num"] = 0
            continue
        c1 = max(1, round(n * 0.25))
        c2 = max(c1 + 1, round(n * 0.70))
        for idx, x in enumerate(grp_items):
            if idx < c1:
                t_num = 1
            elif idx < c2:
                t_num = 2
            else:
                t_num = 3
            # カバレッジ低は最高2軍まで
            if x["scoring"]["coverage"] == "低" and t_num == 1:
                t_num = 2
            # 選定スコア85以上は最低2軍保証
            if x["scoring"]["selection_score"] >= 85.0 and t_num == 3:
                t_num = 2
            x["scoring"]["tier"] = f"{t_num}軍"
            x["scoring"]["tier_num"] = t_num

    # 業種級判定（中央値の分布から上位1/3=A, 中1/3=B, 下1/3=C）
    med_list = sorted(sector_medians.values(), reverse=True)
    if len(med_list) >= 3:
        th_a = med_list[max(0, len(med_list) // 3 - 1)]
        th_b = med_list[max(1, (len(med_list) * 2) // 3 - 1)]
    else:
        th_a, th_b = 85.0, 75.0

    sector_stats: list[dict[str, Any]] = []
    ordered_groups = [g for g in GROUP_ORDER if g in by_grp] + [g for g in by_grp if g not in GROUP_ORDER]
    for grp in ordered_groups:
        grp_items = by_grp[grp]
        med = sector_medians[grp]
        grade = "A" if med >= th_a else ("B" if med >= th_b else "C")
        for x in grp_items:
            x["scoring"]["sector_grade"] = grade
        sector_stats.append(
            {
                "sector_group": grp,
                "count": len(grp_items),
                "median_score": med,
                "grade": grade,
                "tier1": sum(1 for x in grp_items if x["scoring"]["tier_num"] == 1),
                "tier2": sum(1 for x in grp_items if x["scoring"]["tier_num"] == 2),
                "tier3": sum(1 for x in grp_items if x["scoring"]["tier_num"] == 3),
            }
        )

    # 全体順位を付与
    enriched.sort(key=lambda x: (-x["scoring"]["selection_score"], -x["scoring"]["timing_score"], x["code"]))
    for rank, x in enumerate(enriched, start=1):
        x["scoring"]["overall_rank"] = rank

    return enriched, sector_stats
