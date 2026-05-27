#!/usr/bin/env bash
set -euo pipefail

TFVARS="infra/terraform/env/dev.auto.tfvars"
[[ -f "$TFVARS" ]] || { echo "Missing $TFVARS. Run bootstrap first."; exit 1; }

bash scripts/create_lockbox_secrets.sh dev

python3 - <<'PY'
from pathlib import Path
p = Path('infra/terraform/env/dev.auto.tfvars')
t = p.read_text(encoding='utf-8')
if 'function_use_mocks' in t:
    import re
    t = re.sub(r'function_use_mocks\s*=\s*(true|false)', 'function_use_mocks = false', t)
else:
    t += '\nfunction_use_mocks = false\n'
if 'enable_polling_timer' in t:
    import re
    t = re.sub(r'enable_polling_timer\s*=\s*(true|false)', 'enable_polling_timer = false', t)
else:
    t += '\nenable_polling_timer = false\n'
p.write_text(t, encoding='utf-8')
print('Updated dev.auto.tfvars: function_use_mocks=false, enable_polling_timer=false')
PY
echo "Next steps:"
echo "  bash scripts/deploy_all.sh dev"
echo "  bash scripts/seed_functional_dev.sh"
