# MapCamera X100VI 在庫チェック

MapCamera の検索ページを取得し、`X100VI` 周辺の文脈から在庫キーワードを判定するシンプルな CLI スクリプトです。

## 使い方

```bash
python3 mapcamera_x100vi_stock.py
```

### 主なオプション

- `--url`: チェック対象 URL（デフォルトは `https://www.mapcamera.com/search?keyword=X100VI`）
- `--html-file`: ローカル保存したHTMLを読み込んで解析（オフライン検証向け）
- `--keyword`: 商品名キーワード（正規表現、デフォルト `X100VI`）
- `--timeout`: HTTP タイムアウト秒（デフォルト 20）
- `--window`: キーワード前後の抽出文字数（デフォルト 180）

例:

```bash
python3 mapcamera_x100vi_stock.py \
  --url "https://www.mapcamera.com/search?keyword=X100VI" \
  --keyword "X100\\s*VI" \
  --timeout 20 \
  --window 200
```

オフライン例（保存済みHTMLを解析）:

```bash
python3 mapcamera_x100vi_stock.py --html-file ./mapcamera_search.html
```

## 判定ルール

- 在庫あり系キーワード: `在庫あり`, `即納`, `当日出荷`, `注文可能` など
- 在庫なし系キーワード: `在庫なし`, `入荷待ち`, `売り切れ`, `販売終了` など
- JSON-LD の `availability`（例: `InStock`, `OutOfStock`）も補助的に判定
- どちらも含まれない場合は `判定不可`

## 終了コード

- `0`: 在庫あり表記を検出
- `1`: 在庫あり表記を検出できず
- `2`: キーワードを含む商品情報が見つからない
- `3`: 通信エラーやファイル読み込み失敗
- `4`: 引数エラー（不正な正規表現や負の `--window`）

## 注意

- サイト構造変更や動的描画の影響で判定精度が変わる可能性があります。
- このスクリプトは目視確認の補助用途です。最終的には商品ページでの確認を推奨します。
