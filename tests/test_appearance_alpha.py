import subprocess,tempfile,unittest
from pathlib import Path

class AlphaTilesTests(unittest.TestCase):
 def test_exact_alpha_regions_on_partial_tiles(self):
  root=Path(__file__).resolve().parents[1]
  compiler=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
  with tempfile.TemporaryDirectory() as td:
   exe=Path(td)/'alpha.exe'
   build=subprocess.run([str(compiler),'/nologo','/out:'+str(exe),str(root/'mods/RobotomyObserver/MotionAlphaTiles.cs'),str(root/'tests/csharp/AppearanceAlphaTest.cs')],capture_output=True)
   self.assertEqual(build.returncode,0,build.stdout+build.stderr)
   run=subprocess.run([str(exe)],capture_output=True)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr)
   self.assertIn(b'72000 exact rectangle queries passed',run.stdout)
