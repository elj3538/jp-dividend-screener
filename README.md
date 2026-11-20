# 日本株 配当株 軍分けランキング（`jp-dividend-screener`）

東証プライム・スタンダード内国株から配当条件（直近1年実績利回り≥2.0%・時価総額≥300億円・直近5年減配なし）を満たす優良配当株を抽出し、**「選定スコア（配当株としての質）」**と**「買い時スコア（割安度）」**の2軸で評価・軍分けする静的サイト自動生成ツールです。

## 主な特徴
- **JPX公式一覧＋13業種グループ**: 東証33業種を金融3分類（銀行／保険・証券／リース・信販・その他金融）を含む13グループへ集約
- **2軸スコアリング（各0〜110点）＋業種内偏差値**: 業種特性別モデル（一般／銀行／保険・証券／リース・信販）と業種内偏差値を自動算出
- **2段運用（高速日次更新）**: `data/universe.json` による日次自動更新（GitHub Actions・月〜金 19:30 JST）＋ `--rescreen` による定期ユニバース再構築
- **充実のクライアント機能**: 詳細スクリーナー、全体上位50、個別レポート（株価・1株配当推移SVG）、ウォッチリスト、円建て年間予想配当シミュレーター付きポートフォリオ、CSVバックアップ＆復元

## 実行方法
```bash
# 依存インストール
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# テスト実行（先頭40銘柄）
.venv\Scripts\python main.py --limit 40 --workers 4

# 本番ビルド（data/universe.json を用いた日次更新）
.venv\Scripts\python main.py --workers 3

# JPX全銘柄の再スクリーニング（universe.json 再構築）
.venv\Scripts\python main.py --rescreen --workers 3
```
