from pathlib import Path
from string import Template
import yaml

root = Path(__file__).resolve().parents[2]
tpl = (root / 'openapi' / 'api-gateway.yaml.tftpl').read_text()
rendered = Template(tpl).substitute(
    bot_webhook_function_id='f1',
    public_api_function_id='f2',
    admin_api_function_id='f3',
    gateway_service_account_id='sa1',
    public_origin='https://public.example.com',
    admin_origin='https://admin.example.com',
)
spec = yaml.safe_load(rendered)
assert 'paths' in spec
required = [
'/api/v1/bot/webhook',
'/api/v1/public/entrances/{publicCode}',
'/api/v1/public/districts',
'/api/v1/public/districts/{districtId}/houses',
'/api/v1/public/houses/{houseId}/entrances',
'/api/v1/admin/auth/login',
'/api/v1/admin/me',
'/api/v1/admin/districts',
'/api/v1/admin/districts/{districtId}/houses',
'/api/v1/admin/houses/{houseId}/entrances',
'/api/v1/admin/districts/{districtId}/deactivate',
'/api/v1/admin/houses/{houseId}/deactivate',
'/api/v1/admin/entrances/{entranceId}/deactivate',
'/api/v1/admin/test-notification',
]
for p in required:
    assert p in spec['paths'], p
print('openapi ok')
