from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppSettings:
    env: str
    ydb_endpoint: str
    ydb_database: str
    regioncity_base_url: str
    regioncity_map_objects_path: str
    max_api_base_url: str
    max_bot_deeplink_base: str
    public_site_url: str
    admin_site_url: str
    cache_ttl_minutes: int
    polling_interval_minutes: int
    polling_overlap_minutes: int
    max_subscriptions_per_user: int



def load_settings() -> AppSettings:
    return AppSettings(
        env=os.getenv("ENV", "local"),
        ydb_endpoint=os.getenv("YDB_ENDPOINT", ""),
        ydb_database=os.getenv("YDB_DATABASE", ""),
        regioncity_base_url=os.getenv("REGIONCITY_BASE_URL", "https://api.mpoisk.ru/v6/api"),
        regioncity_map_objects_path=os.getenv("REGIONCITY_MAP_OBJECTS_PATH", "/mapObjectManagement/mapObjects"),
        max_api_base_url=os.getenv("MAX_API_BASE_URL", "https://botapi.max.ru"),
        max_bot_deeplink_base=os.getenv("MAX_BOT_DEEPLINK_BASE", ""),
        public_site_url=os.getenv("PUBLIC_SITE_URL", ""),
        admin_site_url=os.getenv("ADMIN_SITE_URL", ""),
        cache_ttl_minutes=int(os.getenv("CACHE_TTL_MINUTES", "10")),
        polling_interval_minutes=int(os.getenv("POLLING_INTERVAL_MINUTES", "5")),
        polling_overlap_minutes=int(os.getenv("POLLING_OVERLAP_MINUTES", "1")),
        max_subscriptions_per_user=int(os.getenv("MAX_SUBSCRIPTIONS_PER_USER", "20")),
    )
