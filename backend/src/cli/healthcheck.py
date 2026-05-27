from composition.container import build_container
from config.version import get_version_info

def main() -> int:
    v = get_version_info()
    print({"status": "ok", "version": v.version, "build": v.build, "commit": v.commit})
    build_container()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
