"""Read-only local observation dashboard; never forwards input."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.live_control import LiveControl
from robotomy.live import LiveReader


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_error(405, "Observation only")

    def do_GET(self):
        if self.path.split('?')[0] == '/state.json':
            status, snapshot = LiveReader(ROOT)._read()
            body = json.dumps({'status': status, 'snapshot': snapshot}, ensure_ascii=False).encode('utf-8')
            content_type = 'application/json; charset=utf-8'
        elif self.path.split('?')[0] == '/frame.png':
            status, body = LiveReader(ROOT).frame()
            if body is None:
                self.send_error(503, 'Game frame unavailable'); return
            content_type = 'image/png'
        elif self.path == '/':
            events = [e for e in LiveControl(ROOT).timeline() if e['kind'] != 'queued'][-20:]
            rows = []
            for event in reversed(events):
                kind = event['kind']
                if kind == 'decision':
                    d = event['decision']
                    message = f"선택: {d['kind']} ({d.get('x')}, {d.get('y')}) {d.get('key') or ''} · {d.get('duration_ms',80)}ms\n이유: {d['rationale']}\n예상: {d['expected']}"
                elif kind == 'outcome': message = event['result']
                elif kind == 'input_receipt':
                    message = {'input_sent':'입력을 전달했습니다. 실제 결과는 후속 화면으로 확인합니다.',
                        'unknown':'입력 결과를 확정할 수 없어 자동 재전송하지 않았습니다.',
                        'rejected':'조건이 맞지 않아 입력을 보내지 않았습니다.'}.get(event['status'],event['status'])
                elif kind == 'human_intervention': message = event.get('message','사용자가 직접 조작했습니다.')
                elif kind == 'operator_pause': message = 'AI의 새 입력을 중지했습니다. 게임 자체를 일시정지하는 기능은 아닙니다.'
                elif kind == 'operator_resume': message = '새 화면을 관찰한 뒤 AI 입력을 다시 요청할 수 있습니다.'
                else: continue
                label = {'decision':'선택과 이유','outcome':'관찰한 결과','input_receipt':'입력 상태',
                    'human_intervention':'사용자 개입','operator_pause':'입력 중지','operator_resume':'입력 재개'}[kind]
                at = datetime.fromisoformat(event['at'].replace('Z','+00:00')).astimezone(timezone(timedelta(hours=9))).strftime('%H:%M:%S KST')
                rows.append(f'<article><small>{html.escape(at)} · {label}</small><pre>{html.escape(message)}</pre></article>')
            current, snapshot = LiveReader(ROOT)._read()
            status = html.escape(json.dumps(current, ensure_ascii=False))
            device = '<p>최신 표시 정보가 없습니다. 화면으로 확인합니다.</p>'
            if snapshot is not None and 'console' in snapshot:
                console = snapshot['console']
                visible = '\n'.join(f"[{v.get('panel', '')}] {v['text']}" for v in snapshot['ui_texts'])
                sounds = '\n'.join(f"#{e['event_id']} {e['kind']} · {e['sound_token'][:8] or e['source_token'][:8]}" for e in console['audio_events'][-8:])
                device = ('<h2>AI에게 전달되는 표시 정보</h2><p>가림 검사에 통과한 세 패널의 문구입니다. '
                          '빈 목록은 정보가 없다는 판정이 아닙니다. 영상과 UI 표본의 시점은 다릅니다.</p><pre>'
                          + html.escape(visible or '(현재 허용된 문구 없음)') + '</pre><h2>최근 소리 이벤트</h2>'
                          '<p>익명 재생 상태 관찰 · 실제 청취나 소리 의미 분석 결과가 아닙니다.</p><pre>'
                          + html.escape(sounds or '(이벤트 없음)') + '</pre>')
                motion = console.get('motion', {})
                lines = []
                for track in motion.get('tracks', []):
                    def vec(key):
                        v = track[key]
                        return '측정 중' if v is None else f"({v['x']:.1f}, {v['y']:.1f})"
                    lines.append(f"{track['track_id'][:8]} · 화면 {vec('screen_velocity')} · 대상 {vec('object_velocity')} · 카메라 {vec('camera_velocity')}")
                device += ('<h2>보이는 표면의 이동 벡터</h2><p>단위: 화면 px/실제 초. 오른쪽 +x, 아래쪽 +y. '
                           '대상 이동과 카메라 이동을 분리합니다. 가림·관찰 만료 시 목록에서 제외됩니다. '
                           '벡터 표본과 위 영상은 시점이 다릅니다.</p><pre>'
                           + html.escape('\n'.join(lines) or '현재 제공되는 벡터 없음 · ' + motion.get('status', '미지원')) + '</pre>')
            paused = (ROOT / '.robotomy/live/control/PAUSED').exists()
            controls = '<p>AI 입력: <strong>' + ('중지됨' if paused else '연결됨 · 요청할 때만 실행') + '</strong></p>'
            body = ('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta http-equiv="refresh" content="2">
<title>Robotomy · 플레이 관찰</title><style>
body{background:#10151c;color:#e6edf3;font:16px system-ui;margin:24px}h1{font-size:24px}
.layout{display:grid;grid-template-columns:1fr 1fr;gap:24px}img{width:100%;border-radius:12px}
article{background:#1c2633;padding:14px;margin:0 0 12px;border-radius:10px}small{color:#91b9ce}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px system-ui}p{color:#abc0cf}
button{background:#e07747;color:#10151c;border:0;padding:12px 18px;border-radius:8px;font-weight:bold;margin-bottom:16px;cursor:pointer}
@media(max-width:900px){.layout{grid-template-columns:1fr}}</style>
<h1>Robotomy · 화면과 판단 기록</h1><p>별도 저장 프로필 · 설명은 행동 전에 기록한 선택 이유입니다.
게임 내부 가상 입력 · 청록색 AI 포인터는 사람 마우스와 분리되어 있습니다. 이 페이지의 클릭은 게임에 전달되지 않습니다.
입력 전송 성공과 게임 내 작업 성공은 구분합니다. 이 페이지는 2초 간격으로 새로 고칩니다.</p>
''' + controls + '''<div class="layout"><section><img src="/frame.png"><p>관찰 전용 화면 · 실제 게임 창에서도 사람 클릭으로 AI 입력을 조작하지 않습니다.</p>
<details><summary>연결 상태</summary><pre>''' + status + '</pre></details></section><section>' + ''.join(rows)
                + '</section></div><section>' + device + '</section></html>').encode('utf-8')
            content_type = 'text/html; charset=utf-8'
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'")
        self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def log_message(self, *_): pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
