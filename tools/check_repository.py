"""Fail CI if runtime data or common credential formats are tracked."""
import re
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
if not any(files):
    print('No tracked files to review. Stage the intended files first.');raise SystemExit(1)
blocked=[]
patterns=[re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(r'github_pat_[A-Za-z0-9_]{30,}'),re.compile(r'gsk_[A-Za-z0-9]{30,}'),re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{30,}'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
for name in filter(None,files):
    path=Path(name)
    if (path.name in {'.env','production.env'} or path.suffix in {'.sqlite3','.db'} or 'venv' in path.parts or 'catalogue-pages' in path.parts or '.vercel' in path.parts):
        blocked.append(name);continue
    if path.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.gif','.ico','.woff','.woff2'}:continue
    content=(root/path).read_text(encoding='utf-8',errors='replace')
    if any(pattern.search(content) for pattern in patterns):blocked.append(name)
if blocked:
    print('Repository check failed. Review these files (credential contents are not printed):')
    print('\n'.join(blocked));raise SystemExit(1)
print('PASS: tracked files exclude private runtime data and common credential patterns.')
