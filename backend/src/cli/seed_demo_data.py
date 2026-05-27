from composition.container import build_container

def main() -> int:
    c = build_container()
    print(c.admin_service.seed_demo_data() if hasattr(c.admin_service, "seed_demo_data") else {"seeded": False})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
