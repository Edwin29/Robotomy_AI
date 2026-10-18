"""Execute production C# hierarchy adapters; full Unity rendering is verified separately."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSC = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'


class MotionTargetsTests(unittest.TestCase):
    @unittest.skipUnless(CSC.exists(), 'requires Windows .NET Framework C# compiler')
    def test_fixture_decoder_preserves_positions_and_null_vectors(self):
        with tempfile.TemporaryDirectory(prefix='robotomy-motion-json-') as directory:
            folder = Path(directory)
            wrapper = folder / 'decode.cs'
            wrapper.write_text('''using System;using System.Globalization;
class Program { static void Main(string[] args) {
var p=MotionProbeSnapshot.Decode(args[0]);Console.WriteLine(p.status+"|"+p.tracks.Length);
foreach(var t in p.tracks) Console.WriteLine(t.track_id+"|"+t.state+"|"+
t.position.x.ToString("R",CultureInfo.InvariantCulture)+"|"+t.position.y.ToString("R",CultureInfo.InvariantCulture)+"|"+
(t.object_velocity==null?"null":t.object_velocity.x.ToString("R",CultureInfo.InvariantCulture)));
}}''', encoding='utf-8')
            exe = folder / 'decode.exe'
            build = subprocess.run([str(CSC), '/nologo', '/target:exe', f'/out:{exe}',
                                    str(ROOT / 'mods/RobotomyObserver/MotionProbeSnapshot.cs'), str(wrapper)],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            tracks = [dict(track_id='a' * 32, state='acquiring', position=dict(x=441.33, y=338.93),
                           bounds=dict(x=440.33, y=337.93, width=2, height=2), interval_ms=0,
                           object_velocity=None, camera_velocity=None, screen_velocity=None),
                      dict(track_id='b' * 32, state='tracking', position=dict(x=633.33, y=338.93),
                           bounds=dict(x=632.33, y=337.93, width=2, height=2), interval_ms=105.29,
                           object_velocity=dict(x=-75.98, y=0), camera_velocity=dict(x=75.98, y=0),
                           screen_velocity=dict(x=0, y=0))]
            result = subprocess.run([str(exe), json.dumps(dict(status='available', tracks=tracks), separators=(',', ':'))],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.splitlines(), [
                'available|2', 'a' * 32 + '|acquiring|441.33|338.93|null',
                'b' * 32 + '|tracking|633.33|338.93|-75.98'])
            empty = subprocess.run([str(exe), '{"status":"available","tracks":[]}'], capture_output=True, text=True)
            self.assertEqual(empty.stdout.strip(), 'available|0')

    @unittest.skipUnless(CSC.exists(), 'requires Windows .NET Framework C# compiler')
    def test_display_branches_and_ownership_lifetime(self):
        with tempfile.TemporaryDirectory(prefix='robotomy-motion-targets-') as directory:
            exe = Path(directory) / 'fixture.exe'
            build = subprocess.run([
                str(CSC), '/nologo', '/target:exe', f'/out:{exe}',
                str(ROOT / 'mods/RobotomyObserver/MotionTargets.cs'),
                str(ROOT / 'tests/fixtures/motion_targets_fixture.cs'),
            ], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS 14 candidate adapter checks', result.stdout)


if __name__ == '__main__':
    unittest.main()
