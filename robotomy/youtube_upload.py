"""Independent, bounded-memory private video uploader. No game/MCP imports.

Windows only for file sharing and credential protection. HTTPS protocol is the
documented YouTube resumable protocol; uncertain completion never starts a duplicate.
"""
import base64
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

SCOPE = 'https://www.googleapis.com/auth/youtube.upload'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
INSERT_URL = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status&notifySubscribers=false'
CHUNK = 4 * 1024 * 1024


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    temp.replace(path)


def protect(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Windows DPAPI required')
    class Blob(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.POINTER(Blob)]
    fn.restype = w.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(result.data)


def sealed(value):
    return base64.b64encode(protect(value.encode('utf8'))).decode('ascii')


def unsealed(value):
    return protect(base64.b64decode(value), True).decode('utf8')


@contextmanager
def closed_recording(path):
    """Read only; refuse any existing writer and prevent new writers until closed.

    Does not request an exclusive write handle, alter NVIDIA, rename, or delete.
    A file busy with recording is left alone, not waited on or force-unlocked.
    """
    if os.name != 'nt':
        raise RuntimeError('Windows sharing checks required')
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                  w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x08000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, 'rb') as stream:
        yield stream


def finalized_mp4(stream):
    """Check bounded top-level atom headers, never decode/load video payloads."""
    size = os.fstat(stream.fileno()).st_size
    seen = set()
    offset = 0
    for _ in range(10000):
        if offset == size:
            return {b'ftyp', b'moov', b'mdat'} <= seen
        if size - offset < 8:
            return False
        stream.seek(offset)
        length, kind = struct.unpack('>I4s', stream.read(8))
        header = 8
        if length == 1:
            extra = stream.read(8)
            if len(extra) != 8:
                return False
            length = struct.unpack('>Q', extra)[0]
            header = 16
        if length == 0:
            length = size - offset
        if length < header or offset + length > size:
            return False
        if kind == b'moov' and length <= header:
            return False
        seen.add(kind)
        offset += length
    return False


def signature(path):
    stat = path.stat()
    return f'{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(method, url, headers, data):
    # Redirects could disclose bearer tokens or upload sessions to other hosts.
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in {'www.googleapis.com', 'oauth2.googleapis.com'}
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('Unexpected Google API endpoint')
    opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        response = opener.open(req, timeout=30)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError('Oversized API response')
        return response.code, dict(response.headers.items()), body


class AuthRequired(Exception):
    pass


class GoogleAuth:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.access = None
        self.expires = 0

    def token(self):
        if self.access and self.expires > time.time() + 60:
            return self.access
        token_path = self.directory/'credentials.dpapi'
        if not token_path.exists():
            raise AuthRequired('Connect Google account first')
        creds = json.loads(protect(token_path.read_bytes(), True))
        fields = {k:creds[k] for k in ('client_id', 'client_secret', 'refresh_token')}
        fields['grant_type'] = 'refresh_token'
        code, _, body = request('POST', TOKEN_URL,
                               {'Content-Type':'application/x-www-form-urlencoded'},
                               urllib.parse.urlencode(fields).encode())
        if code != 200:
            raise AuthRequired(f'Google authorization requires attention (HTTP {code})')
        result = json.loads(body)
        self.access = result['access_token']
        self.expires = time.time() + result.get('expires_in', 3600)
        return self.access


class Uploader:
    def __init__(self, directory, transport=request, auth=None):
        self.directory = Path(directory)
        self.config = json.loads((self.directory/'config.json').read_text(encoding='utf8'))
        self.folder = Path(self.config['folder']).resolve()
        self.transport = transport
        self.auth = auth or GoogleAuth(self.directory)
        self.db = sqlite3.connect(self.directory/'uploads.sqlite3', timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY, signature TEXT, size INTEGER, stable_since REAL,
            state TEXT, session TEXT, offset INTEGER DEFAULT 0, video_id TEXT,
            failures INTEGER DEFAULT 0, next_try REAL DEFAULT 0, note TEXT)''')
        self.db.commit()

    def close(self):
        self.db.close()

    def save(self, name, **fields):
        columns = ','.join(f'{key}=?' for key in fields)
        with self.db:
            self.db.execute(f'UPDATE files SET {columns} WHERE path=?', [*fields.values(), name])

    def files(self):
        for path in sorted(self.folder.glob('*.mp4')):
            # No recursive search and no junction/symlink escape from approved folder.
            if path.is_symlink() or path.resolve().parent != self.folder:
                continue
            if getattr(path.stat(), 'st_file_attributes', 0) & 0x400:
                continue
            yield path

    def scan(self, now=None):
        now = time.time() if now is None else now
        for path in self.files():
            sig, size = signature(path), path.stat().st_size
            row = self.db.execute('SELECT * FROM files WHERE path=?', (path.name,)).fetchone()
            if row is None:
                with self.db:
                    self.db.execute('INSERT INTO files(path,signature,size,stable_since,state) VALUES(?,?,?,?,?)',
                                    (path.name, sig, size, now, 'waiting'))
            elif sig != row['signature'] and row['state'] != 'ignored':
                if row['state'] in {'waiting', 'ready'}:
                    self.save(path.name, signature=sig, size=size, stable_since=now, state='waiting')
                else:
                    self.save(path.name, state='review', note='File changed after upload began; inspect manually')
        return self.summary()

    def summary(self):
        rows = self.db.execute('SELECT path,size,state,offset,video_id,note FROM files ORDER BY path').fetchall()
        return {'folder':str(self.folder), 'privacy':'private',
                'account_connected':(self.directory/'credentials.dpapi').exists(),
                'files':[dict(row) for row in rows]}

    def prepare(self, now=None):
        now = time.time() if now is None else now
        for row in self.db.execute("SELECT * FROM files WHERE state='waiting'").fetchall():
            if row['size'] <= 0 or now - row['stable_since'] < self.config['stable_seconds']:
                continue
            path = self.folder/row['path']
            try:
                with closed_recording(path) as stream:
                    if signature(path) == row['signature'] and finalized_mp4(stream):
                        self.save(row['path'], state='ready', note=None)
            except OSError:
                pass  # Still open for writing, disappeared, or unavailable. Never force access.

    def retry(self, row, note, minimum=0):
        failures = row['failures'] + 1
        delay = max(minimum, min(3600, 30 * 2 ** min(failures, 7)))
        self.save(row['path'], failures=failures, next_try=time.time()+delay, note=note)

    def response(self, row, code, headers, body):
        if code in (200, 201):
            value = json.loads(body)
            video = value.get('id', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
                self.save(row['path'], state='review', note='Completion response missing video ID')
            elif value.get('status', {}).get('privacyStatus') != 'private':
                self.save(row['path'], state='review', video_id=video, note='Unexpected privacy response; inspect YouTube Studio')
            else:
                self.save(row['path'], state='uploaded', video_id=video, offset=row['size'],
                          failures=0, next_try=0, note='Upload accepted; YouTube processing may still be pending')
            return None
        if code == 308:
            value = next((v for k,v in headers.items() if k.lower() == 'range'), None)
            match = re.fullmatch(r'bytes=0-(\d+)', value) if value else None
            if value and not match:
                raise ValueError('Malformed resume range')
            offset = int(match[1])+1 if match else 0
            if not 0 <= offset <= row['size']:
                raise ValueError('Resume offset outside file')
            self.save(row['path'], offset=offset)
            return offset
        if code in (404, 410):
            # Expiry may follow a completed upload whose acknowledgement was lost.
            self.save(row['path'], state='review', note='Session unavailable; check Studio before any new upload')
        elif code == 401:
            self.auth.expires = 0
            self.retry(row, 'Authorization expired or revoked', 300)
        elif code in (403, 429) or 500 <= code <= 599:
            after = next((v for k,v in headers.items() if k.lower() == 'retry-after'), '0')
            delay = int(after) if after.isdigit() else 60
            self.retry(row, f'HTTP {code}; retry deferred', max(delay, 3600 if code == 403 else 60))
        else:
            self.save(row['path'], state='review', note=f'HTTP {code}; manual inspection needed')
        return None

    def step(self):
        """One bounded chunk; persist session before bytes; probe after every restart."""
        row = self.db.execute("SELECT * FROM files WHERE state IN ('ready','uploading') AND next_try<=? ORDER BY path LIMIT 1",
                              (time.time(),)).fetchone()
        if row is None:
            return 'idle'
        try:
            token = self.auth.token()
        except AuthRequired:
            return 'awaiting_auth'
        headers = {'Authorization':'Bearer '+token}
        path = self.folder/row['path']
        try:
            if path.resolve().parent != self.folder or path.is_symlink():
                raise ValueError('Source escaped approved folder')
            with closed_recording(path) as stream:
                if signature(path) != row['signature'] or not finalized_mp4(stream):
                    self.save(row['path'], state='review', note='Source changed or is not finalized')
                    return 'review'
                if row['state'] == 'ready':
                    # This state is written first. A crash with no saved session requires review.
                    self.save(row['path'], state='creating', note='Creating resumable upload')
                    title = Path(row['path']).stem.replace('<','').replace('>','')[:100]
                    metadata = {'snippet':{'title':title, 'description':'Robotomy AI gameplay recording.', 'categoryId':'20'},
                                'status':{'privacyStatus':'private', 'selfDeclaredMadeForKids':False}}
                    code, reply, body = self.transport('POST', INSERT_URL,
                        {**headers, 'Content-Type':'application/json; charset=UTF-8',
                         'X-Upload-Content-Length':str(row['size']), 'X-Upload-Content-Type':'video/mp4'},
                        json.dumps(metadata).encode())
                    if code != 200:
                        # Explicit denial is safe to retry; network ambiguity is not.
                        if code in (401,403,429):
                            self.save(row['path'], state='ready')
                            self.response(row, code, reply, body)
                        else:
                            self.save(row['path'], state='review', note=f'Upload creation HTTP {code}; inspect before retry')
                        return 'deferred'
                    uri = next((v for k,v in reply.items() if k.lower()=='location'), '')
                    parsed = urllib.parse.urlsplit(uri)
                    if (parsed.scheme != 'https' or parsed.netloc != 'www.googleapis.com'
                            or not parsed.path.startswith('/upload/youtube/')):
                        raise ValueError('Unexpected upload session endpoint')
                    self.save(row['path'], state='uploading', session=sealed(uri), offset=0, note=None)
                    row = self.db.execute('SELECT * FROM files WHERE path=?',(row['path'],)).fetchone()
                uri = unsealed(row['session'])
                code, reply, body = self.transport('PUT', uri,
                    {**headers, 'Content-Range':f"bytes */{row['size']}"}, b'')
                offset = self.response(row, code, reply, body)
                if offset is None:
                    return 'checked'
                after = next((v for k,v in reply.items() if k.lower()=='retry-after'), '0')
                if after.isdigit() and int(after) > 0:
                    self.retry(row, 'Server requested retry delay', int(after))
                    return 'deferred'
                if offset == row['size']:
                    self.retry(row, 'All bytes received; awaiting final acknowledgement', 30)
                    return 'deferred'
                stream.seek(offset)
                payload = stream.read(min(CHUNK, row['size']-offset))
                if not payload:
                    raise ValueError('Unexpected end of source')
                code, reply, body = self.transport('PUT', uri,
                    {**headers, 'Content-Type':'video/mp4',
                     'Content-Range':f"bytes {offset}-{offset+len(payload)-1}/{row['size']}"}, payload)
                acknowledged = self.response(row, code, reply, body)
                if acknowledged is not None:
                    if acknowledged <= offset:
                        self.retry(row, 'Server did not advance upload offset', 60)
                    else:
                        self.save(row['path'], failures=0, next_try=0, note=None)
                return 'chunk'
        except (OSError, ValueError, KeyError):
            current = self.db.execute('SELECT * FROM files WHERE path=?',(row['path'],)).fetchone()
            if current['state'] == 'creating':
                self.save(row['path'], state='review', note='Upload creation outcome unknown; no automatic duplicate')
            else:
                self.retry(row, 'Transfer interrupted; next attempt queries saved session')
            return 'deferred'


def initialize(directory, folder, include_existing=False, include_names=()):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory/'config.json').exists():
        raise ValueError('Already initialized; keep the original queue and cutoff')
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError('Recording folder does not exist')
    atomic_json(directory/'config.json', {'folder':str(folder), 'privacy':'private',
        'stable_seconds':120, 'poll_seconds':30, 'chunk_bytes':CHUNK,
        'max_average_mib_per_second':2, 'created_epoch':time.time()})
    uploader = Uploader(directory)
    try:
        uploader.scan()
        if not include_existing:
            for path in uploader.files():
                # Active zero-byte files and files held by a writer stay in the queue.
                if path.stat().st_size == 0 or path.name in include_names:
                    continue
                try:
                    with closed_recording(path) as stream:
                        if finalized_mp4(stream):
                            uploader.save(path.name, state='ignored', note='Completed before automatic upload setup')
                except OSError:
                    pass
        return uploader.summary()
    finally:
        uploader.close()


def worker(directory):
    import msvcrt
    directory = Path(directory)
    with (directory/'worker.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        uploader = Uploader(directory)
        # A crashed initialization may have created a session but not persisted its URI.
        with uploader.db:
            uploader.db.execute("UPDATE files SET state='review', note='Creation interrupted; inspect Studio' WHERE state='creating'")
        next_scan = 0
        try:
            while not (directory/'STOP').exists():
                started = time.monotonic()
                try:
                    if started >= next_scan:
                        uploader.scan(); uploader.prepare()
                        next_scan = started + uploader.config['poll_seconds']
                    state = uploader.step()
                    atomic_json(directory/'status.json', {'pid':os.getpid(), 'at_epoch':time.time(),
                        'worker':state, **uploader.summary()})
                except Exception as exc:
                    # No exception strings: URLs, credentials and remote bodies must not enter logs.
                    state = 'error'
                    atomic_json(directory/'status.json', {'pid':os.getpid(), 'at_epoch':time.time(),
                        'worker':'error', 'error_type':type(exc).__name__})
                delay = max(0, CHUNK/(max(.1, uploader.config['max_average_mib_per_second'])*1024*1024)
                            - (time.monotonic()-started)) if state=='chunk' else 10
                deadline = time.monotonic() + delay
                while time.monotonic() < deadline and not (directory/'STOP').exists():
                    time.sleep(min(1, max(0, deadline-time.monotonic())))
        finally:
            uploader.close()
            atomic_json(directory/'worker-exit.json', {'pid':os.getpid(), 'at_epoch':time.time()})


def authorize(directory):
    """Interactive desktop PKCE flow. Browser login and consent stay with the user."""
    import http.server
    import secrets
    import webbrowser
    directory = Path(directory)
    raw = json.loads((directory/'oauth-client.json').read_text(encoding='utf8'))
    client = raw.get('installed')
    if not client or not client.get('client_id','').endswith('.apps.googleusercontent.com'):
        raise ValueError('Google Desktop OAuth client JSON required')
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    result = {}
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if urllib.parse.urlsplit(self.path).path != '/' or query.get('state') != [state]:
                self.send_error(400); return
            if query.get('code'):
                result['code'] = query['code'][0]
            else:
                result['denied'] = True
            self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers()
            self.wfile.write(b'Return to Robotomy setup. You may close this tab.')
        def log_message(self, *args):
            pass
    with http.server.HTTPServer(('127.0.0.1',0), Handler) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}/'
        params = {'client_id':client['client_id'], 'redirect_uri':redirect,
            'response_type':'code', 'scope':SCOPE, 'state':state, 'access_type':'offline',
            'prompt':'consent select_account', 'code_challenge_method':'S256',
            'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')}
        webbrowser.open('https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(params))
        deadline = time.monotonic()+300
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if 'code' not in result:
        raise AuthRequired('Login cancelled or timed out')
    fields = {'client_id':client['client_id'], 'client_secret':client['client_secret'],
        'code':result['code'], 'code_verifier':verifier, 'redirect_uri':redirect,
        'grant_type':'authorization_code'}
    code, _, body = request('POST', TOKEN_URL, {'Content-Type':'application/x-www-form-urlencoded'},
                            urllib.parse.urlencode(fields).encode())
    if code != 200:
        raise AuthRequired(f'Authorization failed (HTTP {code})')
    value = json.loads(body)
    if not value.get('refresh_token') or (value.get('scope') and SCOPE not in value['scope'].split()):
        raise AuthRequired('Upload permission or offline access was not granted')
    creds = {k:client[k] for k in ('client_id','client_secret')}
    creds['refresh_token'] = value['refresh_token']
    temp = directory/'credentials.tmp'
    temp.write_bytes(protect(json.dumps(creds).encode()))
    temp.replace(directory/'credentials.dpapi')
    return {'status':'connected', 'privacy':'private', 'scope':SCOPE}
