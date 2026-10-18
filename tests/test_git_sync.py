import json
from pathlib import Path
import tempfile
import unittest
from robotomy.git_sync import git, sync_once, VAULT, BRANCH


class GitSyncTests(unittest.TestCase):
    def test_publish_retry_and_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); remote = base/'remote.git'; remote.mkdir()
            git(remote, 'init', '--bare')
            root = base/'source'; root.mkdir(); git(root, 'init')
            git(root, 'remote', 'add', 'origin', str(remote))
            private = root/'.robotomy/experience'; private.mkdir(parents=True)
            (private/'git-sync.json').write_text(json.dumps({'enabled': True, 'remote': str(remote)}))
            vault = root/VAULT; vault.mkdir(parents=True)
            (vault/'note.md').write_text('original', encoding='utf-8')
            (vault/'Media').mkdir(); (vault/'Media/hidden.json').write_text('{}')
            (vault/'save.dat').write_bytes(b'secret')
            (root/'code.py').write_text('unrelated')
            git(root, 'add', 'code.py')
            before = git(root, 'diff', '--cached')
            first = sync_once(root)
            self.assertEqual(first['status'], 'synced')
            self.assertEqual(sync_once(root)['commit'], first['commit'])
            self.assertEqual(git(root, 'diff', '--cached'), before)
            files = git(remote, 'ls-tree', '-r', '--name-only', BRANCH)
            self.assertEqual(files, (VAULT/'note.md').as_posix())
            (vault/'note.md').write_text('correction', encoding='utf-8')
            self.assertNotEqual(sync_once(root)['commit'], first['commit'])
            # A fresh publisher can attach to the existing remote branch.
            root2 = base/'other'; root2.mkdir(); git(root2, 'init')
            git(root2, 'remote', 'add', 'origin', str(remote))
            p2 = root2/'.robotomy/experience'; p2.mkdir(parents=True)
            (p2/'git-sync.json').write_text((private/'git-sync.json').read_text())
            self.assertEqual(sync_once(root2)['status'], 'synced')
            # Remote mismatch never publishes to a different destination.
            git(root, 'remote', 'set-url', 'origin', str(base/'elsewhere'))
            with self.assertRaisesRegex(RuntimeError, 'Remote changed'):
                sync_once(root)


if __name__ == '__main__':
    unittest.main()
