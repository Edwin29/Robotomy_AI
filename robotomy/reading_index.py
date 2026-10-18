"""Human-readable views; ledger IDs and original event payloads stay immutable."""
import json
import re
from pathlib import Path
from .experience import write


def project_reading_views(root):
    vault = Path(root)/'vault/Lobotomy-Experience'
    manifest = vault/'Manifest.json'
    if not manifest.exists(): return []
    attempts = json.loads(manifest.read_text(encoding='utf-8'))['attempts']
    counts = {}; groups = {}; paths = []
    for a in attempts:
        tutorial = a['phase'] == 'tutorial'
        day = a.get('tutorial_segment') or a['day'] if tutorial else a.get('game_day', a['day'])
        kind = 'Tutorials' if tutorial else 'Main'
        key = (a['run'], kind, day)
        counts[key] = counts.get(key, 0)+1
        name = f"{'Tutorial' if tutorial else 'Day'}-{day:02d}-Attempt-{counts[key]:02d}"
        title = f"{'튜토리얼' if tutorial else '본편 Day'} {day} · 시도 {counts[key]}"
        folder = vault/f"Playthroughs/Run-{a['run']:03d}"
        old = a['id'].split('/')[1]
        source = folder/'Days'/f'{old}.md'
        if not source.exists(): continue
        body = source.read_text(encoding='utf-8')
        body = re.sub(r'\A---\n.*?\n---\n', '', body, count=1, flags=re.S)
        body = re.sub(r'^# .*$', '# '+title, body, count=1, flags=re.M)
        body = body.replace(f'./{old}.chat.md', f'./{name}.chat.md')
        body = body.replace('파일 ID는 기존 기록 식별자입니다.', '원본 기록 ID는 연결 보존용입니다.')
        body = f'---\ntitle: {title}\nphase: {"tutorial" if tutorial else "main"}\ngame_day: {"null" if tutorial else day}\nrecord_id: {a["id"]}\nstatus: {a["status"]}\n---\n'+body
        target = folder/kind/f'{name}.md'; write(target, body); paths.append(target)
        chat = folder/'Days'/f'{old}.chat.md'
        if chat.exists():
            text = chat.read_text(encoding='utf-8')
            text = re.sub(r'^# .*$', '# '+title+' · 채팅 원문', text, count=1, flags=re.M)
            target = folder/kind/f'{name}.chat.md'; write(target, text); paths.append(target)
        groups.setdefault(a['run'], {'Tutorials': [], 'Main': []})[kind].append(f'- [{title}]({kind}/{name}.md) — {a["status"]}')
    for run, sections in groups.items():
        target = vault/f'Playthroughs/Run-{run:03d}/README.md'
        write(target, f'# Run {run:03d} 플레이 기록\n\n본편 Day는 실제 게임 날짜입니다. 시도 번호는 튜토리얼과 본편을 각각 셉니다.\n원본 Days/Logs와 기록 ID는 증거 연결을 위해 보존하며, 읽기는 아래 문서를 사용합니다.\n\n## 본편\n\n'+ '\n'.join(sections['Main'])+'\n\n## 튜토리얼\n\n'+'\n'.join(sections['Tutorials'])+'\n')
        paths.append(target)
    return paths
