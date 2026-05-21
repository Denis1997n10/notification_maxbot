from pathlib import Path
import yaml

root = Path(__file__).resolve().parents[2]
spec = yaml.safe_load((root / 'openapi' / 'api-gateway.yaml').read_text())
assert 'paths' in spec
required = [
'/api/v1/bot/webhook',
'/api/v1/public/entrances/{publicCode}',
'/api/v1/public/districts',
'/api/v1/public/districts/{districtId}/houses',
'/api/v1/public/houses/{houseId}/entrances',
'/api/v1/admin/auth/login',
'/api/v1/admin/{proxy+}',
]
for p in required:
    assert p in spec['paths'], p
print('openapi ok')
