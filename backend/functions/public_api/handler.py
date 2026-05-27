from __future__ import annotations

import logging
from typing import Any

from composition.container import api_response, build_container
from config.version import get_version_info

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    path = event.get("path", "")
    method = event.get("httpMethod", "GET")
    params = event.get("pathParameters") or {}

    logger.info("public_api_request", extra={"path": path, "method": method})


    if method == "GET" and path == "/api/v1/system/version":
        return api_response(200, get_version_info().__dict__)
    if method == "GET" and path == "/api/v1/system/health":
        return api_response(200, {"status": "ok"})
    container = build_container()
    if method == "GET" and path.startswith("/api/v1/public/entrances/"):
        return api_response(200, container.public_service.get_entrance_page(params.get("publicCode")))
    if method == "GET" and path == "/api/v1/public/cities":
        return api_response(200, container.public_service.list_cities())
    if method == "GET" and path.startswith("/api/v1/public/cities/") and path.endswith("/districts"):
        return api_response(200, container.public_service.list_city_districts(params.get("cityId")))
    if method == "GET" and path == "/api/v1/public/districts":
        return api_response(200, container.public_service.list_districts())
    if method == "GET" and path.startswith("/api/v1/public/districts/") and path.endswith("/streets"):
        return api_response(200, container.public_service.list_streets(params.get("districtId")))
    if method == "GET" and path.startswith("/api/v1/public/districts/") and path.endswith("/houses"):
        return api_response(200, container.public_service.list_houses(params.get("districtId")))
    if method == "GET" and path.startswith("/api/v1/public/streets/") and path.endswith("/houses"):
        return api_response(200, container.public_service.list_street_houses(params.get("streetId")))
    if method == "GET" and path.startswith("/api/v1/public/houses/") and path.endswith("/entrances"):
        return api_response(200, container.public_service.list_entrances(params.get("houseId")))
    if method == "POST" and path == "/api/v1/public/miniapp/subscriptions":
        result = container.public_service.subscribe_from_mini_app(event.get("body"))
        statuses = {"unauthorized": 401, "not_found": 404, "configuration_error": 500}
        return api_response(statuses.get(result.get("error"), 200), result)
    if method == "POST" and path == "/api/v1/public/subscriptions":
        return api_response(200, container.public_service.create_subscription(event.get("body")))

    return api_response(404, {"error": "not_found"})
