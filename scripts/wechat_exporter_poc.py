from __future__ import annotations

import argparse
import json

from app.services.wechat_exporter_service import WechatArticleExporterService


def main() -> None:
    parser = argparse.ArgumentParser(description="wechat-article-exporter integration PoC")
    parser.add_argument("url", help="WeChat article URL")
    parser.add_argument("--articles", type=int, default=5, help="How many recent articles to query after resolving account")
    args = parser.parse_args()

    service = WechatArticleExporterService()
    if not service.enabled:
        raise SystemExit("WECHAT_EXPORTER_BASE_URL is not configured.")

    account = service.resolve_account_by_url(args.url)
    html = service.download_html(args.url)
    payload: dict[str, object] = {
        "input_url": args.url,
        "html_length": len(html),
        "account": account.__dict__ if account else None,
    }
    if account is not None:
        payload["recent_articles"] = [item.__dict__ for item in service.list_articles(account.fakeid, size=args.articles)]

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
