from pathlib import Path
patterns = ["Subscribe", "Login", "Help", "Notifications", "Settings"]
paths = list(Path('frontend').rglob('*.jsx')) + list(Path('backend/src/application/templates').rglob('*.py'))
bad=[]
for p in paths:
    t=p.read_text(errors='ignore')
    for pat in patterns:
        if pat in t:
            bad.append((str(p),pat))
if bad:
    for b in bad:
        print('WARN',b[0],b[1])
    raise SystemExit(1)
print('russian-facing check ok')
