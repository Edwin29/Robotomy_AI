import json
from pathlib import Path
import shutil
import tempfile
import unittest
from robotomy.experience import journal
from robotomy.playbook import Playbook


class PlaybookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.j=journal(self.root)
        self.p=Playbook(self.root,self.j)
    def entry(self,**extra):
        return {'title':'fixture procedure','author':'test-only',
                'content':{'my_layout':['check visible target',{'tool':'not executed'}]},**extra}
    def test_free_structure_search_revision_and_conflict(self):
        a=self.p.save(self.entry(category='나만의 분류',subject='시험대상',tags=['제압'],summary='검색 요약'))
        self.assertEqual(self.p.read(query='제압',category='나만의 분류')['entries'][0]['id'],a['id'])
        b=self.p.save(self.entry(content='완전히 다른 형식'),a['id'],a['revision'])
        history=self.p.read(entry_id=a['id'],include_history=True)['revisions']
        self.assertEqual(len(history),2);self.assertIsInstance(history[0]['content'],dict)
        self.assertEqual(b['content'],'완전히 다른 형식')
        with self.assertRaisesRegex(ValueError,'conflict'): self.p.save(self.entry(),a['id'],1)
        self.assertFalse(self.j.db_path.exists())
    def test_archive_startup_paging(self):
        a=self.p.save(self.entry(startup=True))
        self.p.save(self.entry(title='other'))
        self.assertEqual(self.p.read(startup_only=True)['total'],1)
        self.assertEqual(self.p.read(limit=1)['next_offset'],1)
        self.p.save(self.entry(status='archived',startup=True),a['id'],1)
        self.assertEqual(self.p.read(startup_only=True)['total'],0)
        self.assertEqual(self.p.read(include_archived=True)['total'],2)
    def test_evidence_unknown_rejected_and_real_link_retained(self):
        with self.assertRaises(ValueError): self.p.save(self.entry(evidence_ids=['fake']))
        self.j.setup()
        with self.j.connect() as db: event=self.j._insert(db,None,'fixture',{'test':True})
        # _insert returns an event ID in this ledger.
        a=self.p.save(self.entry(evidence_ids=[event]))
        self.assertEqual(a['evidence_ids'],[event])
    def test_portable_files_and_export(self):
        a=self.p.save(self.entry())
        self.j.setup();self.j.project()
        bundle=self.j.export();folder=Path(bundle['directory'])
        self.assertTrue((folder/'Playbook'/(a['id']+'.json')).exists())
        manifest=json.loads((folder/'Bundle.json').read_text(encoding='utf8'))
        self.assertIn('Playbook/'+a['id']+'.json',manifest['files'])
        with tempfile.TemporaryDirectory() as other:
            root=Path(other);p=Playbook(root,journal(root));shutil.copytree(self.p.folder,p.folder)
            self.assertEqual(p.read(entry_id=a['id'])['content'],a['content'])
    def test_path_and_size_limits(self):
        with self.assertRaises(ValueError): self.p.read(entry_id='../secret')
        with self.assertRaises(ValueError): self.p.save(self.entry(content='x'*65536))
        with self.assertRaises(ValueError): self.p.save(self.entry(id='overridden'))

if __name__=='__main__':unittest.main()
