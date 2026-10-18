"""Candidate routing checks; rendering and disclosure are tested separately."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSC = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'


class ConsolePanelsTests(unittest.TestCase):
    @unittest.skipUnless(CSC.exists(), 'requires Windows .NET Framework C# compiler')
    def test_only_audited_display_references_are_routed(self):
        with tempfile.TemporaryDirectory(prefix='robotomy-panel-routing-') as directory:
            exe = Path(directory) / 'routing.exe'
            result = subprocess.run([str(CSC), '/nologo', '/target:exe', f'/out:{exe}',
                                     str(ROOT / 'mods/RobotomyObserver/ConsolePanels.cs'),
                                     str(ROOT / 'tests/fixtures/console_panels_fixture.cs')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('PASS 10 panel routing checks', run.stdout)
