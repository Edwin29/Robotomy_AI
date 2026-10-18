"""Isolated, opt-in experience publishing; never stages the developer checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys

BRANCH = 'player-experience'
VAULT = Path('vault/Lobotomy-Experience')


def git(cwd, *args):
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}
    result = subprocess.run(['git', *args], cwd=cwd, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def eligible(path):
    return (path.suffix.lower() in ('.md', '.jsonl', '.json')
            and not any(p.lower() in ('media', '.obsidian') for p in path.parts))


def sync_once(root):
    root = Path(root).resolve()
    config = json.loads((root/'.robotomy/experience/git-sync.json').read_text(encoding='utf-8'))
    if not config.get('enabled'):
        return {'status': 'disabled'}
    remote = git(root, 'remote', 'get-url', 'origin')
    if remote != config['remote']:
        raise RuntimeError('Remote changed; operator review required')
    work = root/'.robotomy/experience/git-publisher'
    work.mkdir(parents=True, exist_ok=True)
    if not (work/'.git').exists():
        git(work, 'init', '-b', BRANCH)
        git(work, 'remote', 'add', 'origin', remote)
        git(work, 'config', 'user.name', 'Robotomy Experience Recorder')
        git(work, 'config', 'user.email', 'robotomy-recorder@localhost')
        git(work, 'config', 'core.autocrlf', 'false')
    if git(work, 'remote', 'get-url', 'origin') != remote:
        raise RuntimeError('Publisher remote mismatch')
    # Never reset, rebase or force-push. Divergence is reported and retained.
    tip = git(work, 'ls-remote', 'origin', 'refs/heads/'+BRANCH)
    if tip:
        git(work, 'fetch', 'origin', 'refs/heads/'+BRANCH)
        git(work, 'merge', '--ff-only', 'FETCH_HEAD')
    from .reading_index import project_reading_views
    project_reading_views(root)
    count = 0
    for source in sorted((root/VAULT).rglob('*')):
        if not source.is_file() or source.is_symlink():
            continue
        rel = source.relative_to(root)
        if not eligible(rel) or not source.resolve().is_relative_to((root/VAULT).resolve()):
            continue
        data = source.read_bytes()
        data.decode('utf-8')  # Refuse binary content disguised as text.
        target = work/rel
        if target.exists() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        git(work, 'add', '--', rel.as_posix())
        count += 1
    staged = git(work, 'diff', '--cached', '--name-only')
    if staged:
        git(work, 'commit', '-m', 'Record player experience')
    # Retrying a previously failed push also works when no new files changed.
    head = git(work, 'rev-parse', '--verify', 'HEAD')
    git(work, 'push', 'origin', 'HEAD:refs/heads/'+BRANCH)
    return {'status': 'synced', 'commit': head, 'changed_files': count, 'branch': BRANCH}


def ensure_sync(root):
    root = Path(root).resolve()
    config = root/'.robotomy/experience/git-sync.json'
    if not config.exists() or not json.loads(config.read_text(encoding='utf-8')).get('enabled'):
        return
    subprocess.Popen([sys.executable, '-X', 'utf8', str(root/'scripts/watch_git_sync.py')],
        cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
