"""yfinanceから日本配当株の株価・配当履歴・財務・決算データを取得しスクリーニング＆キャッシュするモジュール。"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import certifi
import pandas as pd
import requests


def _ensure_ascii_ca_bundle() -> None:
    src = certifi.where()
    try:
        src.encode("ascii")
        return
    except UnicodeEncodeError:
        pass
    dst = Path(tempfile.gettempdir()) / "agy_cacert.pem"
    if not dst.exists() or dst.stat().st_size != Path(src).stat().st_size:
        shutil.copyfile(src, dst)
    os.environ["CURL_CA_BUNDLE"] = str(dst)
    os.environ["SSL_CERT_FILE"] = str(dst)


_ensure_ascii_ca_bundle()

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def fetch_jp10y_yield(cache_dir: Path | None = None) -> float:
    """日本10年国債利回り（%）を stooq から取得する（失敗時は 1.50% フォールバック）。"""
    cache_file = cache_dir / "jp10y.json" if cache_dir else None
    if cache_file and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
        if age_hours <= 20.0:
            try:
                return float(json.loads(cache_file.read_text(encoding="utf-8"))["yield_pct"])
            except Exception:
                pass
    try:
        resp = requests.get("https://stooq.com/q/l/?s=10yjp.b&f=sd2t2ohlcv&h&e=csv", timeout=10)
        if resp.status_code == 200:
            lines = [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
            if len(lines) >= 2:
                cols = lines[1].split(",")
                if len(cols) >= 7:
                    val = _safe_float(cols[6])
                    if val is not None and -0.5 < val < 10.0:
                        val = round(val, 2)
                        if cache_file:
                            cache_file.parent.mkdir(parents=True, exist_ok=True)
                            cache_file.write_text(json.dumps({"yield_pct": val}), encoding="utf-8")
                        return val
    except Exception as exc:
        logger.warning("日本10年国債利回りの取得に失敗（1.50%%を使用）: %s", exc)
    return 1.50


def _extract_series(df: pd.DataFrame | None, candidates: list[str], limit: int = 5) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    row_name = next((name for name in candidates if name in df.index), None)
    if row_name is None:
        return []
    series = df.loc[row_name]
    if isinstance(series, pd.DataFrame):
        series = series.iloc[0]
    cols = sorted(df.columns, key=lambda c: str(c), reverse=True)[:limit]
    result: list[dict[str, Any]] = []
    for col in cols:
        val = _safe_float(series.get(col))
        if val is not None:
            date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
            result.append({"date": date_str, "value": val})
    return result


def _calc_returns_and_technicals(hist: pd.DataFrame | None) -> dict[str, Any]:
    empty = {
        "latest_close": None,
        "latest_date": None,
        "returns": {"D": None, "W": None, "M": None, "3M": None, "6M": None, "9M": None, "Y": None},
        "rsi14": None,
        "macd": None,
        "macd_signal": None,
        "yearly_prices": {},
        "price_series_weekly": [],
    }
    if hist is None or hist.empty or "Close" not in hist.columns:
        return empty

    close = hist["Close"].dropna()
    if close.empty:
        return empty

    latest_close = _safe_float(close.iloc[-1])
    latest_date = close.index[-1].strftime("%Y-%m-%d") if hasattr(close.index[-1], "strftime") else str(close.index[-1])[:10]

    offsets = {"D": 1, "W": 5, "M": 21, "3M": 63, "6M": 126, "9M": 189, "Y": 252}
    returns: dict[str, float | None] = {}
    n = len(close)
    for label, offset in offsets.items():
        if n > offset and latest_close is not None:
            prev = _safe_float(close.iloc[-1 - offset])
            if prev and prev > 0:
                returns[label] = round((latest_close / prev - 1.0) * 100.0, 2)
            else:
                returns[label] = None
        else:
            returns[label] = None

    rsi14 = None
    if n >= 15:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        lg, ll = _safe_float(gain.iloc[-1]), _safe_float(loss.iloc[-1])
        if lg is not None and ll is not None:
            rsi14 = 100.0 if ll == 0 else round(100.0 - (100.0 / (1.0 + lg / ll)), 2)

    macd_val, macd_sig = None, None
    if n >= 35:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        ml = ema12 - ema26
        sl = ml.ewm(span=9, adjust=False).mean()
        mv, sv = _safe_float(ml.iloc[-1]), _safe_float(sl.iloc[-1])
        macd_val = round(mv, 2) if mv is not None else None
        macd_sig = round(sv, 2) if sv is not None else None

    yearly_prices: dict[str, dict[str, float]] = {}
    try:
        idx_years = close.index.year
        for yr in sorted(set(idx_years)):
            sub = close[idx_years == yr]
            if not sub.empty:
                yearly_prices[str(yr)] = {
                    "avg": round(float(sub.mean()), 1),
                    "min": round(float(sub.min()), 1),
                    "max": round(float(sub.max()), 1),
                }
    except Exception:
        pass

    price_series_weekly: list[dict[str, Any]] = []
    try:
        weekly = close.resample("W").last().dropna().tail(260)
        for dt, val in weekly.items():
            v = _safe_float(val)
            if v is not None:
                price_series_weekly.append({"date": dt.strftime("%Y-%m-%d"), "close": round(v, 1)})
    except Exception:
        pass

    return {
        "latest_close": round(latest_close, 1) if latest_close is not None else None,
        "latest_date": latest_date,
        "returns": returns,
        "rsi14": rsi14,
        "macd": macd_val,
        "macd_signal": macd_sig,
        "yearly_prices": yearly_prices,
        "price_series_weekly": price_series_weekly,
    }


def _analyze_dividends(
    divs: pd.Series | None,
    hist: pd.DataFrame | None,
    latest_close: float | None,
    yearly_prices: dict[str, dict[str, float]],
    info: dict[str, Any],
) -> dict[str, Any]:
    """配当履歴から直近1年実績利回り・3年平均利回り・連続増配/非減配・増配率・利回り過去レンジを算出。"""
    now_dt = datetime.now(timezone.utc)
    cur_year = now_dt.year

    annual_divs: dict[int, float] = {}
    ttm_div = 0.0

    if divs is not None and not divs.empty:
        s = divs[divs > 0]
        if not s.empty:
            cutoff = now_dt - timedelta(days=370)
            for dt, val in s.items():
                v = _safe_float(val)
                if v is None or v <= 0:
                    continue
                try:
                    dt_utc = dt.tz_convert("UTC") if getattr(dt, "tzinfo", None) is not None else dt.replace(tzinfo=timezone.utc)
                except Exception:
                    dt_utc = now_dt
                if dt_utc >= cutoff:
                    ttm_div += v
                yr = dt.year
                annual_divs[yr] = round(annual_divs.get(yr, 0.0) + v, 2)

    # 完結済みカレンダー年（前年まで）で連続増配・非減配をカウント
    completed_years = sorted([y for y in annual_divs.keys() if y < cur_year])
    # 最新の未完了年が前年を上回っている場合は含める
    if cur_year in annual_divs and completed_years and annual_divs[cur_year] >= annual_divs[completed_years[-1]] * 0.99:
        eval_years = completed_years + [cur_year]
    else:
        eval_years = completed_years

    consec_increase = 0
    consec_no_cut = 0
    cut_in_last_5y = False

    if len(eval_years) >= 2:
        for i in range(len(eval_years) - 1, 0, -1):
            y_cur, y_prev = eval_years[i], eval_years[i - 1]
            if y_cur - y_prev != 1:
                break
            if annual_divs[y_cur] > annual_divs[y_prev] * 1.005:
                consec_increase += 1
            else:
                break

        for i in range(len(eval_years) - 1, 0, -1):
            y_cur, y_prev = eval_years[i], eval_years[i - 1]
            if y_cur - y_prev != 1:
                break
            if annual_divs[y_cur] >= annual_divs[y_prev] * 0.985:
                consec_no_cut += 1
            else:
                break

        # 直近5年の減配チェック
        recent_years = [y for y in completed_years if y >= cur_year - 5]
        for i in range(1, len(recent_years)):
            y_cur, y_prev = recent_years[i], recent_years[i - 1]
            if annual_divs[y_cur] < annual_divs[y_prev] * 0.985:
                cut_in_last_5y = True
                break
    elif len(eval_years) == 1:
        consec_no_cut = 1

    # 増配率 CAGR（直近5年、取れなければ3年）
    div_cagr_5y = None
    if len(completed_years) >= 2:
        end_y = completed_years[-1]
        start_candidates = [y for y in completed_years if end_y - 5 <= y <= end_y - 3]
        start_y = start_candidates[0] if start_candidates else completed_years[0]
        span = end_y - start_y
        if span >= 1 and annual_divs[start_y] > 0 and annual_divs[end_y] > 0:
            cagr = ((annual_divs[end_y] / annual_divs[start_y]) ** (1.0 / span) - 1.0) * 100.0
            div_cagr_5y = round(max(-50.0, min(80.0, cagr)), 2)

    # 直近1年実績利回り
    ttm_yield = None
    if latest_close and latest_close > 0 and ttm_div > 0:
        ttm_yield = round(ttm_div / latest_close * 100.0, 2)

    # 予想配当利回り
    fwd_rate = _safe_float(info.get("dividendRate"))
    fwd_yield = None
    if fwd_rate and latest_close and latest_close > 0:
        fwd_yield = round(fwd_rate / latest_close * 100.0, 2)
    else:
        raw_dy = _safe_float(info.get("dividendYield"))
        if raw_dy is not None and raw_dy > 0:
            fwd_yield = round(raw_dy if raw_dy > 0.25 else raw_dy * 100.0, 2)
    if fwd_yield is None:
        fwd_yield = ttm_yield

    # 3年平均配当利回り＆過去レンジ位置
    hist_yields: list[float] = []
    recent_3y_yields: list[float] = []
    for y in completed_years[-7:]:
        p_info = yearly_prices.get(str(y))
        d_val = annual_divs.get(y)
        if p_info and p_info.get("avg", 0) > 0 and d_val and d_val > 0:
            yl = round(d_val / p_info["avg"] * 100.0, 2)
            if 0.05 <= yl <= 20.0:
                hist_yields.append(yl)
                if y >= cur_year - 3:
                    recent_3y_yields.append(yl)

    avg_yield_3y = round(sum(recent_3y_yields) / len(recent_3y_yields), 2) if recent_3y_yields else None

    div_yield_range_pos = None
    target_y = fwd_yield or ttm_yield
    if target_y is not None and len(hist_yields) >= 2:
        y_min, y_max = min(hist_yields), max(hist_yields)
        if y_max > y_min:
            # 利回りが高い（上限に近い）ほど割安 = 100%に近い
            div_yield_range_pos = round(max(0.0, min(100.0, (target_y - y_min) / (y_max - y_min) * 100.0)), 1)
        else:
            div_yield_range_pos = 50.0

    annual_series = [{"year": y, "amount": annual_divs[y]} for y in sorted(annual_divs.keys())[-10:]]

    return {
        "ttm_div": round(ttm_div, 2),
        "ttm_yield": ttm_yield,
        "fwd_div": round(fwd_rate, 2) if fwd_rate else (round(ttm_div, 2) if ttm_div > 0 else None),
        "fwd_yield": fwd_yield,
        "avg_yield_3y": avg_yield_3y,
        "consec_increase": consec_increase,
        "consec_no_cut": consec_no_cut,
        "cut_in_last_5y": cut_in_last_5y,
        "div_cagr_5y": div_cagr_5y,
        "div_yield_range_pos": div_yield_range_pos,
        "annual_series": annual_series,
    }


def _evaluate_screen(
    market_cap: float | None,
    div_info: dict[str, Any],
    is_progressive: bool = False,
) -> tuple[bool, str]:
    """日本株配当スクリーニング3条件を判定する。"""
    # 1. 時価総額 300億円以上
    if market_cap is None or market_cap < 30_000_000_000:
        return False, "時価総額300億円未満"

    # 2. 直近1年実績配当利回り 2.0%以上（取れない場合は予想利回り）
    ttm_y = div_info.get("ttm_yield")
    fwd_y = div_info.get("fwd_yield")
    ref_y = ttm_y if ttm_y is not None else fwd_y
    if ref_y is None or ref_y < 2.0:
        return False, f"配当利回り2.0%未満（{ref_y}%）"

    # 補助ルール: 3年平均配当利回り 1.6%以上（算出可能な場合のみ適用）
    avg3y = div_info.get("avg_yield_3y")
    if avg3y is not None and avg3y < 1.6:
        return False, f"3年平均利回り1.6%未満（{avg3y}%）"

    # 3. 直近5年 減配なし（累進配当・DOE宣言は例外）
    if div_info.get("cut_in_last_5y") and not is_progressive:
        return False, "直近5年に減配あり"

    return True, "通過"


def fetch_stock_data(
    constituent: dict[str, Any],
    cache_dir: Path,
    use_cache: bool = True,
    max_age_hours: float = 20.0,
    sleep_sec: float = 0.2,
    skip_non_dividend: bool = True,
) -> dict[str, Any] | None:
    """単一日本株の株価・配当・財務・決算データを取得してスクリーニングする。"""
    code = constituent["code"]
    yf_symbol = constituent.get("yf_symbol", f"{code}.T")
    cache_file = cache_dir / f"{code}.json"

    if use_cache and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
        if age_hours <= max_age_hours:
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                cached["name"] = constituent.get("name", cached.get("name", code))
                cached["sector33"] = constituent.get("sector33", cached.get("sector33", ""))
                cached["sector_group"] = constituent.get("sector_group", cached.get("sector_group", "情報通信・サービス"))
                cached["market"] = constituent.get("market", cached.get("market", ""))
                cached["scale"] = constituent.get("scale", cached.get("scale", ""))
                cached["is_progressive"] = bool(constituent.get("is_progressive", cached.get("is_progressive", False)))
                return cached
            except Exception:
                pass

    if sleep_sec > 0:
        time.sleep(sleep_sec)

    for attempt in range(3):
        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info or {}
            if not info or (not info.get("regularMarketPrice") and not info.get("currentPrice") and not info.get("previousClose")):
                hist = ticker.history(period="5y", auto_adjust=False)
                if hist is None or hist.empty:
                    return None
            else:
                # 高速事前フィルタ（フルスクリーニング時のみ：時価総額300億未満や無配を早期スキップ）
                mkt_pre = _safe_float(info.get("marketCap"))
                dy_pre = _safe_float(info.get("dividendYield"))
                dr_pre = _safe_float(info.get("dividendRate"))
                if skip_non_dividend:
                    if mkt_pre is not None and mkt_pre < 25_000_000_000:
                        return None
                    if (dy_pre is None or dy_pre == 0) and (dr_pre is None or dr_pre == 0):
                        return None
                hist = ticker.history(period="7y", auto_adjust=False)

            tech = _calc_returns_and_technicals(hist)
            latest_close = tech["latest_close"] or _safe_float(info.get("currentPrice")) or _safe_float(info.get("previousClose"))
            if latest_close is None:
                return None

            divs = ticker.dividends
            div_info = _analyze_dividends(divs, hist, latest_close, tech["yearly_prices"], info)
            mkt_cap = _safe_float(info.get("marketCap"))
            is_prog = bool(constituent.get("is_progressive", False))
            screen_passed, screen_reason = _evaluate_screen(mkt_cap, div_info, is_progressive=is_prog)

            if skip_non_dividend and not screen_passed:
                return None

            inc = ticker.income_stmt
            q_inc = ticker.quarterly_income_stmt
            bs = ticker.balance_sheet
            cf = ticker.cashflow

            financials = {
                "revenue": _extract_series(inc, ["Total Revenue", "Operating Revenue"]),
                "operating_income": _extract_series(inc, ["Operating Income", "EBIT"]),
                "ebit": _extract_series(inc, ["EBIT", "Operating Income"]),
                "pretax_income": _extract_series(inc, ["Pretax Income"]),
                "net_income": _extract_series(inc, ["Net Income", "Net Income Common Stockholders"]),
                "eps": _extract_series(inc, ["Diluted EPS", "Basic EPS"]),
                "interest_expense": _extract_series(inc, ["Interest Expense", "Interest Expense Non Operating"]),
            }
            quarterly = {
                "revenue": _extract_series(q_inc, ["Total Revenue", "Operating Revenue"], limit=6),
                "operating_income": _extract_series(q_inc, ["Operating Income", "EBIT"], limit=6),
                "net_income": _extract_series(q_inc, ["Net Income", "Net Income Common Stockholders"], limit=6),
            }
            balance_sheet = {
                "total_debt": _extract_series(bs, ["Total Debt", "Long Term Debt"]),
                "cash": _extract_series(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
                "equity": _extract_series(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity"]),
                "total_assets": _extract_series(bs, ["Total Assets"]),
            }
            cashflow = {
                "operating_cf": _extract_series(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
                "capex": _extract_series(cf, ["Capital Expenditure"]),
                "free_cf": _extract_series(cf, ["Free Cash Flow"]),
                "dividends_paid": _extract_series(cf, ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
                "buybacks": _extract_series(cf, ["Repurchase Of Capital Stock", "Common Stock Payments"]),
            }

            earnings_history: list[dict[str, Any]] = []
            try:
                eh = ticker.earnings_history
                if eh is not None and not eh.empty:
                    for idx_dt, row in eh.tail(4).iterrows():
                        earnings_history.append({
                            "date": idx_dt.strftime("%Y-%m-%d") if hasattr(idx_dt, "strftime") else str(idx_dt)[:10],
                            "eps_actual": _safe_float(row.get("epsActual")),
                            "eps_estimate": _safe_float(row.get("epsEstimate")),
                            "surprise_pct": _safe_float(row.get("surprisePercent")),
                        })
            except Exception:
                pass

            data = {
                "code": code,
                "yf_symbol": yf_symbol,
                "name": constituent.get("name", info.get("shortName") or code),
                "sector33": constituent.get("sector33", ""),
                "sector_group": constituent.get("sector_group", "情報通信・サービス"),
                "market": constituent.get("market", ""),
                "scale": constituent.get("scale", ""),
                "is_progressive": is_prog,
                "screen_passed": screen_passed,
                "screen_reason": screen_reason,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "profile": {
                    "summary_en": info.get("longBusinessSummary", ""),
                    "city": info.get("city", ""),
                    "employees": info.get("fullTimeEmployees"),
                    "website": info.get("website", ""),
                },
                "price": {
                    "current": round(latest_close, 1),
                    "date": tech["latest_date"],
                    "market_cap": mkt_cap,
                    "enterprise_value": _safe_float(info.get("enterpriseValue")),
                    "returns": tech["returns"],
                    "rsi14": tech["rsi14"],
                    "macd": tech["macd"],
                    "macd_signal": tech["macd_signal"],
                    "yearly_prices": tech["yearly_prices"],
                    "price_series_weekly": tech["price_series_weekly"],
                },
                "valuation": {
                    "trailing_pe": _safe_float(info.get("trailingPE")),
                    "forward_pe": _safe_float(info.get("forwardPE")),
                    "price_to_book": _safe_float(info.get("priceToBook")),
                    "roe_info": _safe_float(info.get("returnOnEquity")),
                    "roa_info": _safe_float(info.get("returnOnAssets")),
                    "payout_ratio_info": _safe_float(info.get("payoutRatio")),
                    "target_mean_price": _safe_float(info.get("targetMeanPrice")),
                    "recommendation": info.get("recommendationKey", ""),
                    "analyst_count": info.get("numberOfAnalystOpinions"),
                },
                "dividend": div_info,
                "financials": financials,
                "quarterly": quarterly,
                "balance_sheet": balance_sheet,
                "cashflow": cashflow,
                "earnings_history": earnings_history,
            }

            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "Too Many Requests" in msg:
                wait = 3.0 * (attempt + 1)
                logger.warning("[%s] レート制限(429)のため %.1f秒待機してリトライ", code, wait)
                time.sleep(wait)
                continue
            logger.debug("[%s] 取得エラー: %s", code, exc)
            return None
    return None
