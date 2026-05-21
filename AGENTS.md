# Mandatory project context (user-defined)

This file defines mandatory context for the entire repository tree.
Any conflicting implementation decision must be explicitly escalated to the user before proceeding.

## Product framing
You are building a **serverless resident notification platform**.

Do **not** implement this as a narrow cleaning bot.
Implement it as a **generic subscription and notification platform** for task/event notifications related to directory objects.

## Current MVP
- source = regioncity
- real external API = MPOISK / RegionCity
- base API URL = `https://api.mpoisk.ru/v6/api`
- task source endpoint = `/taskManagement/tasks`
- task detail endpoint = `/taskManagement/tasks/{taskID}`
- cleaning task type = `taskTypeID=51`
- completed task status = `status=3`
- subject type = entrance
- notification channel = max

## Core abstractions
- Subject / Directory Object
- Subscription
- TaskEvent
- NotificationPayload
- NotificationChannel
- ExternalTaskProvider
- TemplateProvider
- Repositories through interfaces
- Hexagonal/layered architecture
- SOLID

## Architecture rules
- Domain and application layers must not depend on YDB, MAX, RegionCity/MPOISK, Yandex Cloud, HTTP framework, or Cloud Function event structures.
- Infrastructure adapters implement ports.
- Cloud Function handlers must be thin.
- No business logic in handlers.
- No YDB queries outside repository adapters.
- No MAX-specific code in use cases.
- No RegionCity raw payloads outside RegionCity infrastructure adapter and mapper.
- Use Yandex Lockbox for secrets.
- Do not store apartments.
- Do not store photos.
- Do not store detailed per-user delivery logs.
- Use processed external task IDs to prevent duplicate processing.
- Use soft deactivation instead of hard deletion.
- Use Cloud Logs for operational logs.

## RegionCity/MPOISK mapping rules
- `taskID` maps to `TaskEvent.external_id` and `processed_events.external_id`.
- `taskTypeID=51` identifies cleaning tasks.
- `status=3` identifies completed cleaning tasks for MVP.
- `mapObjectID` maps to `entrance.regioncity_external_ref` and is the primary way to match external tasks to entrances.
- `subscriberID` must be stored only as raw metadata if needed, not used as entrance ID.
- `title`/`address`/`description` are display/raw metadata fields.
- `lastStatusChangeDate` maps to `TaskEvent.occurred_at`.
- `customFieldFormItems` must be converted to metadata dict by name.
- `worker-id` must never be shown to residents.
- `ml-verdict` may be stored as metadata but must not be shown to residents unless explicitly enabled later.
- `customStatusID` must be stored as metadata but not used as the main completion decision unless later confirmed by business.
- Photo URLs are not present in the provided task payload. Implement image handling as optional and extensible, but do not invent an API endpoint for photos.

## MVP constraints
- Users subscribe to entrances.
- One user can have up to 20 active subscriptions.
- QR opens public entrance page.
- Public page shows latest 10 cleaning events.
- Public page uses short cache, default 10 minutes.
- Bot allows subscribe/list/unsubscribe/disable all/help/services placeholder.
- Services are only architecturally reserved for future feature flags.
- Admin roles: `super_admin` and `district_admin`.
- District admins manage only assigned districts.
