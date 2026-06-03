from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta

from composition.container import build_container


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--exclude-last-minutes", type=int, default=25)
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()

    date_to = datetime.now(UTC) - timedelta(minutes=args.exclude_last_minutes)
    date_from = date_to - timedelta(days=args.days)
    container = build_container()
    result = asyncio.run(container.polling_use_case.execute(date_from=date_from, date_to=date_to, notify=args.notify))
    print(json.dumps({"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "notify": args.notify, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
