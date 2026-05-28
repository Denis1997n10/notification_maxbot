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
        "login_conflict": 409,
    }
    return api_response(status_by_error.get(result.get("error"), 400) if "error" in result else success_status, result)


def _path_param(params: dict[str, Any], path: str, key: str, marker: str) -> str:
    if params.get(key):
        return str(params[key])
    parts = path.strip("/").split("/")
    try:
        index = parts.index(marker)
    except ValueError:
        return ""
    return parts[index + 1] if len(parts) > index + 1 else ""


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
    if path == "/api/v1/admin/cities" and method == "GET":
        return _admin_response(container.admin_service.list_cities(headers))
    if path == "/api/v1/admin/cities" and method == "POST":
        return _admin_response(container.admin_service.create_city(headers, body), 201)
    if path.startswith("/api/v1/admin/cities/") and path.endswith("/districts") and method == "GET":
        return _admin_response(container.admin_service.list_city_districts(headers, _path_param(params, path, "cityId", "cities")))
    if path.startswith("/api/v1/admin/cities/") and path.endswith("/districts") and method == "POST":
        return _admin_response(container.admin_service.create_city_district(headers, _path_param(params, path, "cityId", "cities"), body), 201)
    if path.startswith("/api/v1/admin/cities/") and path.endswith("/districts/assign") and method == "POST":
        return _admin_response(container.admin_service.assign_district_to_city(headers, _path_param(params, path, "cityId", "cities"), body))
    if path.startswith("/api/v1/admin/cities/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_city(headers, _path_param(params, path, "cityId", "cities")))
    if path == "/api/v1/admin/districts/unassigned" and method == "GET":
        return _admin_response(container.admin_service.list_unassigned_districts(headers))
    if path == "/api/v1/admin/districts" and method == "GET":
        return _admin_response(container.admin_service.list_districts(headers))
    if path == "/api/v1/admin/districts" and method == "POST":
        return _admin_response(container.admin_service.create_district(headers, body), 201)
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/houses") and method == "GET":
        return _admin_response(container.admin_service.list_houses(headers, _path_param(params, path, "districtId", "districts")))
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/houses") and method == "POST":
        return _admin_response(container.admin_service.create_house(headers, _path_param(params, path, "districtId", "districts"), body), 201)
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/streets") and method == "GET":
        return _admin_response(container.admin_service.list_streets(headers, _path_param(params, path, "districtId", "districts")))
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/streets") and method == "POST":
        return _admin_response(container.admin_service.create_street(headers, _path_param(params, path, "districtId", "districts"), body), 201)
    if path.startswith("/api/v1/admin/streets/") and path.endswith("/houses") and method == "GET":
        return _admin_response(container.admin_service.list_street_houses(headers, _path_param(params, path, "streetId", "streets")))
    if path.startswith("/api/v1/admin/streets/") and path.endswith("/houses") and method == "POST":
        return _admin_response(container.admin_service.create_street_house(headers, _path_param(params, path, "streetId", "streets"), body), 201)
    if path.startswith("/api/v1/admin/houses/") and path.endswith("/entrances") and method == "GET":
        return _admin_response(container.admin_service.list_entrances(headers, _path_param(params, path, "houseId", "houses")))
    if path.startswith("/api/v1/admin/houses/") and path.endswith("/entrances") and method == "POST":
        return _admin_response(container.admin_service.create_entrance(headers, _path_param(params, path, "houseId", "houses"), body), 201)
    if path.startswith("/api/v1/admin/districts/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_district(headers, _path_param(params, path, "districtId", "districts")))
    if path.startswith("/api/v1/admin/streets/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_street(headers, _path_param(params, path, "streetId", "streets")))
    if path.startswith("/api/v1/admin/houses/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_house(headers, _path_param(params, path, "houseId", "houses")))
    if path.startswith("/api/v1/admin/entrances/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_entrance(headers, _path_param(params, path, "entranceId", "entrances")))
    if path == "/api/v1/admin/users" and method == "GET":
        return _admin_response(container.admin_service.list_resident_users(headers))
    if path.startswith("/api/v1/admin/users/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_resident_user(headers, _path_param(params, path, "userId", "users")))
    if path == "/api/v1/admin/admin-users" and method == "GET":
        return _admin_response(container.admin_service.list_admin_users(headers))
    if path == "/api/v1/admin/admin-users" and method == "POST":
        return _admin_response(container.admin_service.create_admin_user(headers, body), 201)
    if path.startswith("/api/v1/admin/admin-users/") and path.endswith("/deactivate") and method == "PATCH":
        return _admin_response(container.admin_service.deactivate_admin_user(headers, _path_param(params, path, "adminId", "admin-users")))
    if method == "POST" and path == "/api/v1/admin/test-notification":
        return _admin_response(container.admin_service.send_test_notification(headers, body))

    return api_response(404, {"error": "not_found"})
