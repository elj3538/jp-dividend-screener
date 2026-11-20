"""JPX「東証上場銘柄一覧」からプライム・スタンダード内国株と13業種グループを取得するモジュール。"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

JPX_PAGE_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
JPX_LIST_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xlsx"

# 東証33業種 → 参考サイト準拠の独自13業種グループ（金融を銀行・保険証券・リースの3分類に分離）
SECTOR33_TO_GROUP: dict[str, str] = {
    "電気・ガス業": "資源・エネルギー",
    "鉱業": "資源・エネルギー",
    "石油・石炭製品": "資源・エネルギー",
    "金属製品": "素材",
    "繊維製品": "素材",
    "化学": "素材",
    "ガラス・土石製品": "素材",
    "鉄鋼": "素材",
    "非鉄金属": "素材",
    "パルプ・紙": "素材",
    "ゴム製品": "素材",
    "電気機器": "機械・電機",
    "精密機器": "機械・電機",
    "機械": "機械・電機",
    "輸送用機器": "自動車・輸送機",
    "卸売業": "商社・卸",
    "情報・通信業": "情報通信・サービス",
    "サービス業": "情報通信・サービス",
    "その他製品": "情報通信・サービス",
    "小売業": "生活必需・小売",
    "食料品": "生活必需・小売",
    "水産・農林業": "生活必需・小売",
    "医薬品": "医薬・ヘルスケア",
    "建設業": "建設・不動産",
    "不動産業": "建設・不動産",
    "陸運業": "インフラ・運輸",
    "空運業": "インフラ・運輸",
    "海運業": "インフラ・運輸",
    "倉庫・運輸関連業": "インフラ・運輸",
    "銀行業": "銀行",
    "保険業": "保険・証券",
    "証券、商品先物取引業": "保険・証券",
    "証券・商品先物取引業": "保険・証券",
    "その他金融業": "リース・信販・その他金融",
}

GROUP_ORDER: list[str] = [
    "資源・エネルギー",
    "素材",
    "機械・電機",
    "自動車・輸送機",
    "商社・卸",
    "情報通信・サービス",
    "銀行",
    "保険・証券",
    "リース・信販・その他金融",
    "生活必需・小売",
    "医薬・ヘルスケア",
    "建設・不動産",
    "インフラ・運輸",
]

SCALE_PRIORITY: dict[str, int] = {
    "TOPIX Core30": 1,
    "TOPIX Large70": 2,
    "TOPIX Mid400": 3,
    "TOPIX Small 1": 4,
    "TOPIX Small 2": 5,
}

TOPIX500_SCALES = {"TOPIX Core30", "TOPIX Large70", "TOPIX Mid400"}
TOPIX1000_SCALES = {"TOPIX Core30", "TOPIX Large70", "TOPIX Mid400", "TOPIX Small 1"}

# 代表的な累進配当・DOE宣言銘柄（公式IRベースの例示リスト。減配例外判定・表示用）
PROGRESSIVE_DIV_CODES: set[str] = {
    "8058", "8001", "8031", "8053", "8002",  # 5大商社
    "8306", "8316", "8411",  # 3メガバンク
    "8766", "8725", "8630",  # 3メガ損保
    "9432", "9433", "9434",  # 通信大手
    "8591", "8593", "8439", "8566",  # リース大手
    "1925", "1928", "1801", "1802", "1812",  # 建設・住宅
    "2914", "4502", "4503", "5020", "1605",  # JT・医薬・資源
    "7203", "7267", "6501", "6503", "4063", "4452", "4911",
}

# オフライン・テスト用フォールバック（日本の代表高配当・連続増配株）
FALLBACK_CONSTITUENTS: list[dict[str, str]] = [
    {"code": "8058", "yf_symbol": "8058.T", "name": "三菱商事", "sector33": "卸売業", "sector_group": "商社・卸", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "8001", "yf_symbol": "8001.T", "name": "伊藤忠商事", "sector33": "卸売業", "sector_group": "商社・卸", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "8031", "yf_symbol": "8031.T", "name": "三井物産", "sector33": "卸売業", "sector_group": "商社・卸", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "8306", "yf_symbol": "8306.T", "name": "三菱UFJフィナンシャル・グループ", "sector33": "銀行業", "sector_group": "銀行", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "8316", "yf_symbol": "8316.T", "name": "三井住友フィナンシャルグループ", "sector33": "銀行業", "sector_group": "銀行", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "8411", "yf_symbol": "8411.T", "name": "みずほフィナンシャルグループ", "sector33": "銀行業", "sector_group": "銀行", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "8766", "yf_symbol": "8766.T", "name": "東京海上ホールディングス", "sector33": "保険業", "sector_group": "保険・証券", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "8725", "yf_symbol": "8725.T", "name": "MS&ADインシュアランスグループHD", "sector33": "保険業", "sector_group": "保険・証券", "market": "プライム（内国株式）", "scale": "TOPIX Large70"},
    {"code": "8591", "yf_symbol": "8591.T", "name": "オリックス", "sector33": "その他金融業", "sector_group": "リース・信販・その他金融", "market": "プライム（内国株式）", "scale": "TOPIX Large70"},
    {"code": "8593", "yf_symbol": "8593.T", "name": "三菱HCキャピタル", "sector33": "その他金融業", "sector_group": "リース・信販・その他金融", "market": "プライム（内国株式）", "scale": "TOPIX Mid400"},
    {"code": "9432", "yf_symbol": "9432.T", "name": "日本電信電話", "sector33": "情報・通信業", "sector_group": "情報通信・サービス", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "9433", "yf_symbol": "9433.T", "name": "KDDI", "sector33": "情報・通信業", "sector_group": "情報通信・サービス", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "9434", "yf_symbol": "9434.T", "name": "ソフトバンク", "sector33": "情報・通信業", "sector_group": "情報通信・サービス", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "2914", "yf_symbol": "2914.T", "name": "日本たばこ産業", "sector33": "食料品", "sector_group": "生活必需・小売", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "1925", "yf_symbol": "1925.T", "name": "大和ハウス工業", "sector33": "建設業", "sector_group": "建設・不動産", "market": "プライム（内国株式）", "scale": "TOPIX Large70"},
    {"code": "1928", "yf_symbol": "1928.T", "name": "積水ハウス", "sector33": "建設業", "sector_group": "建設・不動産", "market": "プライム（内国株式）", "scale": "TOPIX Large70"},
    {"code": "1605", "yf_symbol": "1605.T", "name": "INPEX", "sector33": "鉱業", "sector_group": "資源・エネルギー", "market": "プライム（内国株式）", "scale": "TOPIX Large70"},
    {"code": "4502", "yf_symbol": "4502.T", "name": "武田薬品工業", "sector33": "医薬品", "sector_group": "医薬・ヘルスケア", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "4503", "yf_symbol": "4503.T", "name": "アステラス製薬", "sector33": "医薬品", "sector_group": "医薬・ヘルスケア", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "7203", "yf_symbol": "7203.T", "name": "トヨタ自動車", "sector33": "輸送用機器", "sector_group": "自動車・輸送機", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "7267", "yf_symbol": "7267.T", "name": "本田技研工業", "sector33": "輸送用機器", "sector_group": "自動車・輸送機", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "4063", "yf_symbol": "4063.T", "name": "信越化学工業", "sector33": "化学", "sector_group": "素材", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
    {"code": "4452", "yf_symbol": "4452.T", "name": "花王", "sector33": "化学", "sector_group": "素材", "market": "プライム（内国株式）", "scale": "TOPIX Large70"},
    {"code": "6501", "yf_symbol": "6501.T", "name": "日立製作所", "sector33": "電気機器", "sector_group": "機械・電機", "market": "プライム（内国株式）", "scale": "TOPIX Core30"},
]


def fetch_jpx_prime_standard(
    cache_dir: Path | None = None,
    use_cache: bool = True,
    limit: int | None = None,
    topix500_only: bool = False,
    topix1000_only: bool = False,
) -> list[dict[str, Any]]:
    """JPX東証上場銘柄一覧からプライム・スタンダード内国株を取得する。"""
    cache_file = cache_dir / "jpx_prime_standard.json" if cache_dir else None
    items: list[dict[str, Any]] = []

    if use_cache and cache_file and cache_file.exists():
        logger.info("キャッシュからJPX銘柄一覧を読み込みます: %s", cache_file)
        items = json.loads(cache_file.read_text(encoding="utf-8"))
    else:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            }
            resp = requests.get(JPX_LIST_URL, headers=headers, timeout=30)
            resp.raise_for_status()
            df = pd.read_excel(io.BytesIO(resp.content))

            for _, row in df.iterrows():
                market = str(row.get("市場・商品区分", "")).strip()
                if market not in ("プライム（内国株式）", "スタンダード（内国株式）"):
                    continue
                raw_code = str(row.get("コード", "")).strip()
                if raw_code.endswith(".0"):
                    raw_code = raw_code[:-2]
                if not raw_code or raw_code == "nan":
                    continue
                sec33 = str(row.get("33業種区分", "")).strip()
                group = SECTOR33_TO_GROUP.get(sec33, "情報通信・サービス")
                name = str(row.get("銘柄名", raw_code)).strip()
                scale = str(row.get("規模区分", "-")).strip()
                items.append(
                    {
                        "code": raw_code,
                        "yf_symbol": f"{raw_code}.T",
                        "name": name,
                        "sector33": sec33,
                        "sector_group": group,
                        "market": market,
                        "scale": scale,
                        "is_progressive": raw_code in PROGRESSIVE_DIV_CODES,
                    }
                )
            # 規模区分優先（大型株から先に処理されるよう整列）
            items.sort(key=lambda x: (SCALE_PRIORITY.get(x["scale"], 9), 0 if "プライム" in x["market"] else 1, x["code"]))
            logger.info("JPX公式一覧から プライム・スタンダード内国株 %d 件を取得しました。", len(items))
            if cache_file and items:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("JPX一覧の取得に失敗したためフォールバックを使用します: %s", exc)
            items = [dict(x, is_progressive=x["code"] in PROGRESSIVE_DIV_CODES) for x in FALLBACK_CONSTITUENTS]

    if topix500_only:
        items = [x for x in items if x.get("scale") in TOPIX500_SCALES]
    elif topix1000_only:
        items = [x for x in items if x.get("scale") in TOPIX1000_SCALES]

    return items[:limit] if limit else items
