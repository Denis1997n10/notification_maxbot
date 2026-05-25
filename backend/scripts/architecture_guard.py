from pathlib import Path

checks = []

def has(pattern, text):
    return pattern in text

for p in Path('backend/src/domain').rglob('*.py'):
    t = p.read_text()
    checks.append(('domain_imports_infra', 'infrastructure.' not in t, str(p)))

for p in Path('backend/src/application').rglob('*.py'):
    t = p.read_text()
    checks.append(('application_imports_infra', 'infrastructure.' not in t, str(p)))

for p in Path('backend/functions').rglob('handler.py'):
    t = p.read_text()
    checks.append(('no_direct_ydb_query', 'SELECT ' not in t and 'UPSERT ' not in t, str(p)))

full = '\n'.join(Path('.').rglob('*').__class__.__name__ for _ in [0])
# direct file scans
repo_text = ''
for p in Path('backend').rglob('*'):
    if p.is_file() and p.suffix in {'.py', '.sql', '.md', '.tf', '.yaml', '.yml'}:
        repo_text += '\n' + p.read_text(errors='ignore')

checks += [
    ('no_github_only_prod_build', 'runs-on: [self-hosted' in (Path(__file__).resolve().parents[2] / '.github/workflows/deploy-prod.yml').read_text(), '.github/workflows/deploy-prod.yml'),
    ('no_hardcoded_regioncity_token', 'REGIONCITY_API_TOKEN=' not in repo_text, 'repo'),
    ('no_apartments_table', 'CREATE TABLE IF NOT EXISTS apartments' not in repo_text, 'repo'),
    ('no_photo_storage_table', 'CREATE TABLE IF NOT EXISTS photos' not in repo_text, 'repo'),
    ('no_hard_delete_endpoints', 'DELETE /api/' not in repo_text, 'repo'),
]

failed = [c for c in checks if not c[1]]
if failed:
    for name, _, where in failed:
        print('FAIL', name, where)
    raise SystemExit(1)
print('architecture guard ok')
