# Operations

- Polling timer runs every 20 minutes.
- One MAX bot only: production webhook must point to production gateway.
- Use admin test notifications for safe production checks.

## Logs to monitor
- RegionCity API errors (`RegionCity request failed`)
- MAX send errors (`max_request_failed`, `max_image_send_failed_fallback_to_text`)
- Polling errors and low fetched/processed counters
- Admin auth failures in `admin_api`
