import tempfile,unittest,shutil
from pathlib import Path
from robotomy.reload_host import ReloadHost,HOT,PINNED

class VisualReloadTests(unittest.IsolatedAsyncioTestCase):
 async def test_name_and_read_survive_real_generation_reload(self):
  with tempfile.TemporaryDirectory() as td:
   source=Path(td)/'code';source.mkdir();original=Path(__file__).resolve().parents[1]/'robotomy'
   for name in set(HOT+PINNED):shutil.copy2(original/(name+'.py'),source/(name+'.py'))
   host=ReloadHost(Path(td),source);await host.initialize()
   try:
    names={x.name for x in await host.tools()}
    self.assertTrue({'name_visual','read_visual_names'}<=names)
    item={'ref':'mark:'+'a'*20,'kind':'mark','label':'표식'}
    host.backend._player_adapter.visual_names.decorate([item])
    result=await host.call('name_visual',{'ref':item['ref'],'name':'가면','description':'내 관찰에 붙인 이름'})
    self.assertNotIn('isError": true',str(result))
    revision=host.revision;p=source/'appearance.py';p.write_text(p.read_text(encoding='utf8')+'\n# new implementation generation\n',encoding='utf8')
    await host.call('reload_player_code',{});self.assertNotEqual(revision,host.revision)
    result=await host.call('read_visual_names',{'query':'가면'})
    self.assertIn('가면',str(result));self.assertNotIn('ModuleNotFoundError',str(result))
   finally:host.discard(host.prefix)

if __name__=='__main__':unittest.main()
