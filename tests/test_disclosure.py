"""Execute production UI disclosure guards, independent of game-model values."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSC = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'


class DisclosureTests(unittest.TestCase):
    @unittest.skipUnless(CSC.exists(), 'requires Windows .NET Framework C# compiler')
    def test_production_disclosure_guards(self):
        with tempfile.TemporaryDirectory(prefix='robotomy-disclosure-') as directory:
            exe = Path(directory) / 'fixture.exe'
            build = subprocess.run([str(CSC), '/nologo', '/target:exe', f'/out:{exe}',
                                    str(ROOT / 'mods/RobotomyObserver/ConsoleDisclosure.cs'),
                                    str(ROOT / 'tests/fixtures/disclosure_fixture.cs')],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS 51 disclosure checks', result.stdout)


if __name__ == '__main__':
    unittest.main()
