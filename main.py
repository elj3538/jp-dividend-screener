"""日本株 配当株 軍分けランキング スクリーナー メイン実行スクリプト。"""

from __future__ import annotations

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.fetch_data import fetch_jp10y_yield, fetch_stock_data
from src.fetch_jpx import fetch_jpx_prime_standard
from src.generate_pages import generate_auxiliary_pages
from src.generate_reports import generate_reports
from src.generate_site import generate_site
from src.scoring import score_all_stocks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="日本株 配当株 軍分けランキング 静的サイト生成ツール")
    parser.add_argument("--limit", type=int, default=None, help="取得対象銘柄数の上限（テスト用）")
    parser.add_argument("--topix500-only", action="store_true", help="TOPIX 500 のみを母集団にする（高速モード）")
    parser.add_argument("--topix1000-only", action="store_true", help="TOPIX 1000 のみを母集団にする")
    parser.add_argument("--rescreen", action="store_true", help="JPX全銘柄を再スキャンして data/universe.json を更新")
    parser.add_argument("--no-cache", action="store_true", help="ローカルキャッシュを無視して再取得")
    parser.add_argument("--workers", type=int, default=3, help="並列取得ワーカー数（デフォルト: 3）")
    args = parser.parse_args()

    t0 = time.time()
    base_dir = Path(__file__).resolve().parent
    cache_dir = base_dir / "cache"
    data_dir = base_dir / "data"
    dist_dir = base_dir / "dist"
    universe_file = data_dir / "universe.json"
    use_cache = not args.no_cache

    logger.info("=== 日本株 配当株 軍分けランキング 生成開始 ===")
    jp10y_yield = fetch_jp10y_yield(cache_dir=cache_dir)
    logger.info("日本10年国債利回り: %.2f%%", jp10y_yield)

    use_universe = (
        not args.rescreen
        and not args.topix500_only
        and not args.topix1000_only
        and args.limit is None
        and universe_file.exists()
    )

    if use_universe:
        u_data = json.loads(universe_file.read_text(encoding="utf-8"))
        constituents = u_data.get("constituents", [])
        logger.info("data/universe.json から %d 銘柄を読み込みました（日次更新モード）", len(constituents))
    else:
        constituents = fetch_jpx_prime_standard(
            cache_dir=cache_dir,
            use_cache=use_cache,
            limit=args.limit,
            topix500_only=args.topix500_only,
            topix1000_only=args.topix1000_only,
        )
        logger.info("母集団取得完了: %d 銘柄（スクリーニングモード）", len(constituents))

    passed_stocks: list[dict] = []
    done_cnt = 0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        future_map = {
            pool.submit(
                fetch_stock_data,
                c,
                cache_dir,
                use_cache=use_cache,
                sleep_sec=0.20,
                skip_non_dividend=not use_universe,
            ): c
            for c in constituents
        }
        for fut in as_completed(future_map):
            done_cnt += 1
            res = fut.result()
            if res is not None:
                if res.get("screen_passed") or use_universe:
                    if res.get("price", {}).get("current"):
                        passed_stocks.append(res)
            if done_cnt % 100 == 0 or done_cnt == len(constituents):
                logger.info(
                    "進捗: %d / %d 銘柄処理済み（通過: %d 銘柄）",
                    done_cnt,
                    len(constituents),
                    len(passed_stocks),
                )

    logger.info("スクリーニング完了: %d 銘柄が対象", len(passed_stocks))
    if not passed_stocks:
        logger.error("対象銘柄が0件のため終了します。")
        return

    # スクリーニング完了時（--limit 指定なし）に data/universe.json を保存
    if not use_universe and args.limit is None:
        data_dir.mkdir(parents=True, exist_ok=True)
        u_payload = {
            "mode": "topix500" if args.topix500_only else ("topix1000" if args.topix1000_only else "prime_standard"),
            "count": len(passed_stocks),
            "constituents": [
                {
                    "code": s["code"],
                    "yf_symbol": s["yf_symbol"],
                    "name": s["name"],
                    "sector33": s.get("sector33", ""),
                    "sector_group": s.get("sector_group", "情報通信・サービス"),
                    "market": s.get("market", ""),
                    "scale": s.get("scale", ""),
                    "is_progressive": bool(s.get("is_progressive", False)),
                }
                for s in passed_stocks
            ],
        }
        universe_file.write_text(json.dumps(u_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("data/universe.json を保存しました（%d 銘柄）", len(passed_stocks))

    items, sector_stats = score_all_stocks(passed_stocks, jp10y_yield=jp10y_yield)
    logger.info("採点・業種内偏差値・軍分け完了（対象グループ数: %d）", len(sector_stats))

    index_path = generate_site(items, sector_stats, dist_dir=dist_dir, jp10y_yield=jp10y_yield)
    report_cnt = generate_reports(items, dist_dir=dist_dir, jp10y_yield=jp10y_yield)
    generate_auxiliary_pages(dist_dir=dist_dir, jp10y_yield=jp10y_yield)

    elapsed = time.time() - t0
    logger.info(
        "=== 完了（%.1f秒）: %s / 個別レポート %d 件 / 補助ページ4件 ===",
        elapsed,
        index_path,
        report_cnt,
    )


if __name__ == "__main__":
    main()
