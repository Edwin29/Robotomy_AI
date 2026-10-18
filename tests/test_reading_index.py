import tempfile,json,unittest
from pathlib import Path
from robotomy.reading_index import project_reading_views

class ReadingIndexTests(unittest.TestCase):
 def test_separates_tutorial_and_corrected_day_without_mutating_evidence(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); v=root/'vault/Lobotomy-Experience'; f=v/'Playthroughs/Run-001'; (f/'Days').mkdir(parents=True)
   attempts=[dict(id='Run-001/Day-01-Attempt-01',run=1,day=1,phase='tutorial',status='completed'),dict(id='Run-001/Day-04-Attempt-01',run=1,day=4,game_day=1,phase='story',status='completed'),dict(id='Run-001/Day-03-Attempt-02',run=1,day=3,game_day=3,phase='story',status='playing')]
   (v/'Manifest.json').write_text(json.dumps({'attempts':attempts}))
   for a in attempts:
    name=a['id'].split('/')[1]; (f/'Days'/f'{name}.md').write_text(f'---\nday: {a["day"]}\n---\n# {name}\n\n[chat](./{name}.chat.md)\n[log](../Logs/{name}.jsonl)')
    (f/'Days'/f'{name}.chat.md').write_text('# old\n\n원문 그대로',encoding='utf-8')
   before={p:p.read_bytes() for p in (f/'Days').iterdir()}
   project_reading_views(root)
   self.assertTrue((f/'Tutorials/Tutorial-01-Attempt-01.md').exists())
   main=(f/'Main/Day-01-Attempt-01.md').read_text(encoding='utf-8')
   self.assertIn('game_day: 1',main); self.assertIn('record_id: Run-001/Day-04-Attempt-01',main)
   self.assertIn('./Day-01-Attempt-01.chat.md',main)
   self.assertIn('status: playing',(f/'Main/Day-03-Attempt-01.md').read_text(encoding='utf-8'))
   self.assertEqual(before,{p:p.read_bytes() for p in before})
   project_reading_views(root)
   self.assertEqual(main,(f/'Main/Day-01-Attempt-01.md').read_text(encoding='utf-8'))
