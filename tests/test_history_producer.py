"""Exercise production C# disk workers, independent of game simulation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows production publication API')
class HistoryProducerTests(unittest.TestCase):
    def test_production_worker_wrap_failure_and_pause_gap(self):
        compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'history-test.exe'
            build = subprocess.run([str(compiler), '/nologo', '/target:exe', f'/out:{target}',
                '/reference:System.Web.Extensions.dll',
                str(ROOT/'mods/RobotomyObserver/ConsolePublisher.cs'),
                str(ROOT/'mods/RobotomyObserver/ConsoleHistory.cs'),
                str(ROOT/'tests/csharp/HistoryHarness.cs')], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout+build.stderr)
            result = subprocess.run([str(target), str(Path(folder)/'cache')],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

