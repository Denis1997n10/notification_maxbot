from composition.container import build_container

def main() -> int:
    c = build_container()
    print(c.notification_service.send_batch({"test": True}) if hasattr(c.notification_service, "send_batch") else {"sent": False})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
