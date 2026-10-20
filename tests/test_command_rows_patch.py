import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from robotomy.live import command_rows, validate_snapshot
import test_console

ROOT = Path(__file__).resolve().parents[1]


class CommandRowsPatchTests(unittest.TestCase):
    def test_display_values_and_coordinates_survive_transport(self):
        test_console.ConsoleContractTests.setUp(self)
        fields = {'name': '직원', 'hp': '30/32', 'sp': '35/35',
                  'success_rate': '측정불가', 'work_time': '보통'}
        template = self.obj['ui_texts'][0]
        self.obj['ui_texts'] = [dict(template, panel='command', row_id='7', role=k, text=v)
                                for k, v in fields.items()]
        self.obj['buttons'] = [dict(template, panel='command', row_id='7', role='click', interactable=True)]
        snapshot, _ = validate_snapshot(self.obj)
        row = command_rows(snapshot)[0]
        for k, v in fields.items():
            self.assertEqual(row[k], v)
        self.assertEqual(row['click']['x'], template['x'] + template['width']/2)
        # New empty observation must not reuse employee rows from earlier frames.
        self.assertEqual(command_rows({'ui_texts': [], 'buttons': []}), [])

    def test_actual_cover_map_preserves_opaque_and_partial_occlusion(self):
        csc = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not csc.exists(): self.skipTest('Windows C# compiler required')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'test.cs').write_text('''using System;
class Test { static void Main() {
 byte[] alpha=new byte[100]; for(int i=0;i<100;i++) alpha[i]=32;
 alpha[55]=255; alpha[77]=64;
 var m=new CoverAlphaMap(alpha,10,10);
 if(!m.Clear(0,0,5,5)) throw new Exception("light tint blocked");
 if(m.Clear(0,0,10,10)) throw new Exception("opaque icon leaked");
 if(m.Clear(5,5,6,6)) throw new Exception("partial cover leaked");
 if(m.Clear(7,7,8,8)) throw new Exception("dense tint leaked");
 if(m.Clear(-1,0,3,3)) throw new Exception("invalid bounds accepted");
 Console.WriteLine("PASS");
} }''', encoding='utf-8')
            result = subprocess.run([str(csc), '/nologo', f'/out:{p / "test.exe"}',
                str(ROOT/'mods/RobotomyObserver/CoverAlphaMap.cs'), str(p/'test.cs')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            result = subprocess.run([str(p/'test.exe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
