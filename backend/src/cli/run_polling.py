from datetime import UTC, datetime, timedelta
from composition.container import build_container

def main() -> int:
    c = build_container()
    now = datetime.now(UTC)
    df = now - timedelta(minutes=25)
    if hasattr(c.polling_use_case, "execute"):
        print(c.polling_use_case.execute(date_from=df, date_to=now))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
