#!/usr/bin/env python3
"""マップカメラでFUJIFILM X100VIの在庫状況を確認するCLI。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from html import unescape
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_URL = "https://www.mapcamera.com/search?keyword=X100VI"
DEFAULT_TIMEOUT = 20
DEFAULT_WINDOW = 180

IN_STOCK_KEYWORDS = (
    "在庫あり",
    "在庫有",
    "即納",
    "当日出荷",
    "翌日出荷",
    "注文可能",
)

OUT_OF_STOCK_KEYWORDS = (
    "在庫なし",
    "入荷待ち",
    "お取り寄せ",
    "販売終了",
    "予約受付終了",
    "売り切れ",
)


@dataclass
class ProductStatus:
    title: str
    snippet: str
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


def normalize_text(value: str) -> str:
    text = unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_stock(text: str) -> bool | None:
    for kw in IN_STOCK_KEYWORDS:
        if kw in text:
            return True
    for kw in OUT_OF_STOCK_KEYWORDS:
        if kw in text:
            return False
    return None


def find_keyword_contexts(text: str, keyword_pattern: str, window: int) -> list[str]:
    contexts: list[str] = []
    for match in re.finditer(keyword_pattern, text, flags=re.IGNORECASE):
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        snippet = text[start:end].strip()
        if snippet:
            contexts.append(snippet)
    return contexts


def extract_json_product_candidates(html: str) -> list[str]:
    candidates: list[str] = []
    for raw in re.findall(
        r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>([\s\S]*?)</script>",
        html,
        flags=re.IGNORECASE,
    ):
        body = raw.strip()
        if not body:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue

        def walk(node: object) -> Iterable[dict]:
            if isinstance(node, dict):
                yield node
                for v in node.values():
                    yield from walk(v)
            elif isinstance(node, list):
                for item in node:
                    yield from walk(item)

        for item in walk(payload):
            name = str(item.get("name", ""))
            avail = str(item.get("availability", ""))
            if not name:
                continue
            if re.search(r"X100\s*VI", name, flags=re.IGNORECASE):
                raw_candidate = f"{name} {avail}".strip()
                candidates.append(raw_candidate)
    return candidates


def build_statuses(html: str, keyword_pattern: str, window: int) -> list[ProductStatus]:
    # script/styleを落とした通常テキスト
    reduced_html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    reduced_html = re.sub(r"<style[\s\S]*?</style>", " ", reduced_html, flags=re.IGNORECASE)
    plain_text = normalize_text(reduced_html)

    contexts = find_keyword_contexts(plain_text, keyword_pattern, window)

    # 構造化データからも拾う（検索結果が動的生成でも最低限ヒントを取る）
    contexts.extend(extract_json_product_candidates(html))

    uniq: list[str] = []
    seen: set[str] = set()
    for c in contexts:
        norm = normalize_text(c)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        uniq.append(norm)

    statuses: list[ProductStatus] = []
    for snippet in uniq:
        title_match = re.search(r"[^\n]*X100\s*VI[^\n]*", snippet, flags=re.IGNORECASE)
        title = title_match.group(0).strip() if title_match else "X100VI"
        statuses.append(ProductStatus(title=title[:140], snippet=snippet[:220], in_stock=detect_stock(snippet)))

    return statuses


def summarize(statuses: list[ProductStatus], keyword_label: str) -> int:
    if not statuses:
        print(f"{keyword_label} を含む商品情報が見つかりませんでした。URLやページ構造を確認してください。")
        return 2

    has_in_stock = any(s.in_stock is True for s in statuses)

    print(f"=== MapCamera 在庫チェック ({keyword_label}) ===")
    for i, st in enumerate(statuses, start=1):
        state = "判定不可"
        if st.in_stock is True:
            state = "在庫ありの可能性"
        elif st.in_stock is False:
            state = "在庫なし/要確認"

        print(f"[{i}] {state}: {st.title}")
        print(f"    抜粋: {st.snippet}")

    if has_in_stock:
        print("\n結果: 在庫あり表記が検出されました。")
        return 0

    print("\n結果: 在庫あり表記は検出できませんでした。")
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MapCameraでX100VIの在庫状況を確認")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"チェック対象URL (default: {DEFAULT_URL})")
    parser.add_argument("--keyword", default="X100VI", help="商品キーワード（正規表現）。default: X100VI")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTPタイムアウト秒")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW, help="キーワード前後の抽出文字数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        html = fetch_html(args.url, args.timeout)
    except HTTPError as exc:
        print(f"HTTPエラー: {exc.code} {exc.reason}", file=sys.stderr)
        return 3
    except URLError as exc:
        print(f"URLエラー: {exc.reason}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"取得エラー: {exc}", file=sys.stderr)
        return 3

    statuses = build_statuses(html, args.keyword, args.window)
    return summarize(statuses, args.keyword)


if __name__ == "__main__":
    raise SystemExit(main())
