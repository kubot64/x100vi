#!/usr/bin/env python3
"""マップカメラでFUJIFILM X100VIの在庫状況を確認するスクリプト。"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_URL = "https://www.mapcamera.com/search?keyword=X100VI"
DEFAULT_TIMEOUT = 20

# 在庫を示すキーワード（先に肯定判定）
IN_STOCK_KEYWORDS = [
    "在庫あり",
    "在庫有",
    "即納",
    "当日出荷",
    "翌日出荷",
]

OUT_OF_STOCK_KEYWORDS = [
    "在庫なし",
    "入荷待ち",
    "お取り寄せ",
    "販売終了",
    "予約受付終了",
]


@dataclass
class ProductStatus:
    title: str
    line: str
    in_stock: bool | None


def fetch_html(url: str, timeout: int) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(req, timeout=timeout) as res:
        charset = res.headers.get_content_charset() or "utf-8"
        return res.read().decode(charset, errors="replace")


def normalize_text(html: str) -> str:
    text = re.sub(r"<script[\\s\\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text


def detect_stock_from_line(line: str) -> bool | None:
    for kw in IN_STOCK_KEYWORDS:
        if kw in line:
            return True
    for kw in OUT_OF_STOCK_KEYWORDS:
        if kw in line:
            return False
    return None


def extract_x100vi_lines(text: str) -> list[str]:
    parts = re.split(r"(?<=[。\|])|\s{2,}", text)
    found = []
    for part in parts:
        p = part.strip()
        if not p:
            continue
        if re.search(r"X100\s*VI", p, flags=re.IGNORECASE):
            found.append(p)
    return found


def build_statuses(lines: list[str]) -> list[ProductStatus]:
    statuses = []
    for line in lines:
        m = re.search(r"(FUJIFILM|富士フイルム)?[^\n]*X100\s*VI[^\n]*", line, flags=re.IGNORECASE)
        title = m.group(0).strip() if m else "X100VI"
        statuses.append(ProductStatus(title=title, line=line, in_stock=detect_stock_from_line(line)))
    return statuses


def summarize(statuses: list[ProductStatus]) -> int:
    if not statuses:
        print("X100VIを含む商品行が見つかりませんでした。URLやページ構造を確認してください。")
        return 2

    has_in_stock = any(s.in_stock is True for s in statuses)

    print("=== Map Camera X100VI 在庫チェック ===")
    for i, st in enumerate(statuses, start=1):
        if st.in_stock is True:
            stock_label = "在庫ありの可能性"
        elif st.in_stock is False:
            stock_label = "在庫なし/要確認"
        else:
            stock_label = "判定不可"
        print(f"[{i}] {stock_label}: {st.title}")
        print(f"    抜粋: {st.line[:160]}")

    if has_in_stock:
        print("\n結果: X100VIの在庫あり表記が検出されました。")
        return 0

    print("\n結果: 在庫あり表記は検出できませんでした。")
    return 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MapCameraでX100VIの在庫状況を確認")
    p.add_argument("--url", default=DEFAULT_URL, help=f"チェック対象URL (default: {DEFAULT_URL})")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTPタイムアウト秒")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        html = fetch_html(args.url, args.timeout)
    except HTTPError as e:
        print(f"HTTPエラー: {e.code} {e.reason}", file=sys.stderr)
        return 3
    except URLError as e:
        print(f"URLエラー: {e.reason}", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001
        print(f"取得エラー: {e}", file=sys.stderr)
        return 3

    text = normalize_text(html)
    lines = extract_x100vi_lines(text)
    statuses = build_statuses(lines)
    return summarize(statuses)


if __name__ == "__main__":
    raise SystemExit(main())
