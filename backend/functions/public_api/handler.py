from __future__ import annotations

import logging
from typing import Any

from composition.container import api_response, build_container

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    path = event.get("path", "")
    method = event.get("httpMethod", "GET")
    params = event.get("pathParameters") or {}

    logger.info("public_api_request", extra={"path": path, "method": method})

    if method == "GET" and path.startswith("/api/v1/public/entrances/"):
        return api_response(200, container.public_service.get_entrance_page(params.get("publicCode")))
    if method == "GET" and path == "/api/v1/public/districts":
        return api_response(200, container.public_service.list_districts())
    if method == "GET" and path.startswith("/api/v1/public/districts/") and path.endswith("/houses"):
        return api_response(200, container.public_service.list_houses(params.get("districtId")))
    if method == "GET" and path.startswith("/api/v1/public/houses/") and path.endswith("/entrances"):
        return api_response(200, container.public_service.list_entrances(params.get("houseId")))
    if method == "POST" and path == "/api/v1/public/subscriptions":
        return api_response(200, container.public_service.create_subscription(event.get("body")))

    return api_response(404, {"error": "not_found"})
