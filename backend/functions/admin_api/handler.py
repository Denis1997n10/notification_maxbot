from __future__ import annotations

import logging
from typing import Any

from composition.container import api_response, build_container

logger = logging.getLogger(__name__)


def _admin_response(result: dict, success_status: int = 200) -> dict[str, Any]:
    status_by_error = {
        "unauthorized": 401,
        "forbidden": 403,
        "not_found": 404,
        "public_code_conflict": 409,
    }
    return api_response(status_by_error.get(result.get("error"), 400) if "error" in result else success_status, result)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    path = event.get("path", "")
    method = event.get("httpMethod", "GET")
    params = event.get("pathParameters") or {}
    headers = event.get("headers") or {}
    body = event.get("body")

    logger.info("admin_api_request", extra={"path": path, "method": method})

    if method == "POST" and path == "/api/v1/admin/auth/login":
        result = container.admin_service.login(body)
        return api_response(401 if "error" in result else 200, result)
    if method == "GET" and path == "/api/v1/admin/me":
        result = container.admin_service.me(headers)
        return api_response(401 if "error" in result else 200, result)
    if path == "/api/v1/admin/districts" and method == "GET":
        return _admin_response(container.admin_service.list_districts(headers))
    if path == "/api/v1/admin/districts" and method == "POST":
        return _admin_response(container.admin_service.create_district(headers, body), 201)
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/houses") and method == "GET":
        return _admin_response(container.admin_service.list_houses(headers, params.get("districtId", "")))
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/houses") and method == "POST":
        return _admin_response(container.admin_service.create_house(headers, params.get("districtId", ""), body), 201)
    if path.startswith("/api/v1/admin/houses/") and path.endswith("/entrances") and method == "GET":
        return _admin_response(container.admin_service.list_entrances(headers, params.get("houseId", "")))
    if path.startswith("/api/v1/admin/houses/") and path.endswith("/entrances") and method == "POST":
        return _admin_response(container.admin_service.create_entrance(headers, params.get("houseId", ""), body), 201)
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_district(headers, params.get("districtId", "")))
    if path.startswith("/api/v1/admin/houses/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_house(headers, params.get("houseId", "")))
    if path.startswith("/api/v1/admin/entrances/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_entrance(headers, params.get("entranceId", "")))
    if method == "POST" and path == "/api/v1/admin/test-notification":
        return _admin_response(container.admin_service.send_test_notification(headers, body))

    return api_response(404, {"error": "not_found"})
