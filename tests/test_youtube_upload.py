"""No Google network and no real recording writes. All media is synthetic."""
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import patch

from robotomy import youtube_upload as y


def mp4(payload=1024):
    def atom(kind, data):
        return struct.pack('>I4s', len(data)+8, kind)+data
    return atom(b'ftyp', b'isom0000')+atom(b'mdat', b'x'*payload)+atom(b'moov', b'test0000')


class Token:
    expires = 0
    def token(self):
        return 'fixture-not-a-real-token'


@unittest.skipUnless(os.name=='nt','Windows uploader')
class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media = self.root/'media'; self.media.mkdir()
        self.state = self.root/'private'
        self.file = self.media/'current.mp4'; self.file.write_bytes(mp4())
        y.initialize(self.state, self.media, include_names=['current.mp4'])
        self.u = y.Uploader(self.state, auth=Token())
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.u.close)

    def ready(self):
        self.u.prepare(time.time()+121)
        self.assertEqual(self.row()['state'], 'ready')

    def row(self):
        return self.u.db.execute('SELECT * FROM files WHERE path=?',('current.mp4',)).fetchone()

    def complete(self):
        return 200, {}, json.dumps({'id':'testvideo01','status':{'privacyStatus':'private'}}).encode()

    def test_dpapi_roundtrip(self):
        cipher = y.protect(b'fixture secret')
        self.assertNotIn(b'fixture secret',cipher)
        self.assertEqual(y.protect(cipher,True), b'fixture secret')

    def test_init_skips_old_but_tracks_explicit_current_and_future(self):
        old = self.media/'old.mp4';old.write_bytes(mp4())
        other = self.root/'second'
        result = y.initialize(other,self.media,include_names=['current.mp4'])
        self.assertEqual({f['path']:f['state'] for f in result['files']},
                         {'current.mp4':'waiting','old.mp4':'ignored'})
        with self.assertRaises(ValueError): y.initialize(other,self.media)
        new = self.media/'new.mp4';new.write_bytes(b'')
        self.u.scan();self.u.prepare(time.time()+500)
        rows = {r['path']:r for r in self.u.summary()['files']}
        self.assertEqual(rows['new.mp4']['state'],'waiting')

    def test_busy_writer_never_ready_even_if_size_is_stable(self):
        with self.file.open('r+b'):
            self.u.prepare(time.time()+500)
            self.assertEqual(self.row()['state'],'waiting')
            with self.assertRaises(OSError):
                with y.closed_recording(self.file): pass
        self.ready()

    def test_quiet_time_resets_on_change_and_incomplete_mp4_is_rejected(self):
        self.u.prepare();self.assertEqual(self.row()['state'],'waiting')
        self.file.write_bytes(mp4()+b'partial')
        self.u.scan();self.u.prepare(time.time()+500)
        self.assertEqual(self.row()['state'],'waiting')
        self.file.write_bytes(mp4(2000));self.u.scan()
        self.u.prepare();self.assertEqual(self.row()['state'],'waiting')
        self.ready()

    def test_missing_auth_never_sends_http(self):
        self.ready();self.u.auth=y.GoogleAuth(self.state)
        self.u.transport=lambda *a: self.fail('No network before authorization')
        self.assertEqual(self.u.step(),'awaiting_auth')

    def test_private_upload_native_protocol_and_no_duplicate(self):
        self.ready();calls=[]
        def api(method,url,headers,body):
            calls.append((method,headers,body))
            if method=='POST':
                metadata=json.loads(body)
                self.assertEqual(metadata['status']['privacyStatus'],'private')
                self.assertIn('notifySubscribers=false',url)
                return 200, {'Location':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test'}, b''
            if not body: return 308, {}, b''
            self.assertEqual(body,self.file.read_bytes())
            self.assertEqual(headers['Content-Range'],f'bytes 0-{len(body)-1}/{len(body)}')
            return self.complete()
        self.u.transport=api;self.u.step()
        self.assertEqual(self.row()['state'],'uploaded')
        self.assertEqual(self.u.step(),'idle')
        self.assertEqual(len(calls),3)
        self.assertEqual(self.file.read_bytes(),mp4())

    def test_interruption_recovers_server_offset_without_new_session(self):
        self.ready();stage=[]
        def api(method,url,headers,body):
            stage.append(method)
            if method=='POST': return 200, {'Location':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test'},b''
            if not body: return 308,{},b''
            raise OSError('Connection lost after server received some bytes')
        self.u.transport=api;self.u.step()
        self.assertEqual(self.row()['state'],'uploading')
        self.u.save('current.mp4',next_try=0)
        def resumed(method,url,headers,body):
            self.assertEqual(method,'PUT')
            if not body: return 308,{'Range':'bytes=0-255'},b''
            self.assertTrue(headers['Content-Range'].startswith('bytes 256-'))
            self.assertEqual(body,self.file.read_bytes()[256:])
            return self.complete()
        self.u.transport=resumed;self.u.step()
        self.assertEqual(self.row()['state'],'uploaded')

    def test_lost_final_ack_recovers_complete_response(self):
        self.ready();self.u.save('current.mp4',state='uploading',session=y.sealed('https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test'))
        def api(method,url,headers,body):
            self.assertEqual(body,b'');return self.complete()
        self.u.transport=api;self.u.step()
        self.assertEqual(self.row()['state'],'uploaded')

    def test_ambiguous_creation_and_expired_session_do_not_reupload(self):
        self.ready()
        self.u.transport=lambda *a: (_ for _ in ()).throw(OSError('ambiguous creation'))
        self.u.step();self.assertEqual(self.row()['state'],'review')
        self.assertEqual(self.u.step(),'idle')
        self.u.save('current.mp4',state='uploading',session=y.sealed('https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test'))
        self.u.transport=lambda *a: (404,{},b'')
        self.u.step();self.assertEqual(self.row()['state'],'review')
        self.assertEqual(self.u.step(),'idle')

    def test_changed_uploaded_file_requires_review(self):
        self.u.save('current.mp4',state='uploaded',video_id='testvideo01')
        self.file.write_bytes(mp4(2048));self.u.scan()
        self.assertEqual(self.row()['state'],'review')

    def test_chunk_limit_and_source_replacement_before_send(self):
        self.file.write_bytes(mp4(y.CHUNK+512));self.u.scan();self.ready()
        calls=[]
        def api(method,url,headers,body):
            if method=='POST':return 200,{'Location':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=t'},b''
            if not body:return 308,{},b''
            calls.append(len(body));return 308,{'Range':f'bytes=0-{len(body)-1}'},b''
        self.u.transport=api;self.u.step();self.assertEqual(calls,[y.CHUNK])
        self.file.write_bytes(mp4())
        self.u.transport=lambda *a:self.fail('Changed source must not send bytes')
        self.u.step();self.assertEqual(self.row()['state'],'review')

    def test_malicious_session_and_range_are_rejected(self):
        self.ready();self.u.transport=lambda *a:(200,{'Location':'https://example.com/steal'},b'')
        self.u.step();self.assertEqual(self.row()['state'],'review')
        with self.assertRaises(ValueError): y.request('PUT','https://example.com',{},b'')
        with self.assertRaises(ValueError): self.u.response(self.row(),308,{'Range':'bytes=0-99999999'},b'')

    def test_quota_backoff_and_bad_privacy(self):
        self.ready();row=self.row()
        self.u.response(row,403,{},b'')
        self.assertGreater(self.row()['next_try'],time.time()+3500)
        self.u.response(row,200,{},b'{"id":"testvideo01","status":{"privacyStatus":"public"}}')
        self.assertEqual(self.row()['state'],'review')


if __name__=='__main__':unittest.main()
