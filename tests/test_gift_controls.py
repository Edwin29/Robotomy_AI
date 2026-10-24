import copy,unittest
from robotomy.live import reading_panels,_ui_items
from robotomy.quick_input import resolve
from robotomy.perception import changes
class GiftsTests(unittest.TestCase):
 def test_state_input_and_clear(self):
  def text(role,value,slot='7'):return dict(panel='gift',row_id=slot,role=role,text=value,x=10,y=20,width=50,height=20)
  raw=[text('employee','A','window'),text('name','gift'),text('region','head'),text('locked','false'),text('lock_available','true')]
  s={'ui_texts':_ui_items(raw,100),'buttons':_ui_items([{**text('lock','toggle'), 'target_id':'88','interactable':True,'input_verified':True,'hit_x':35,'hit_y':30}],100,True)}
  p=reading_panels(s);row=p['gifts']['slots']['7'];self.assertIs(row['locked'],False);self.assertEqual(resolve(s,row['lock_click']['ref'])['target_id'],'88')
  n=copy.deepcopy(s);n['ui_texts'][3]['text']='true';self.assertIn({'set':['gifts','slots','7','locked'],'value':True},changes(p,reading_panels(n)))
  n['ui_texts']=[];n['buttons']=[];self.assertIsNone(reading_panels(n)['gifts'])
 def test_disabled_has_no_target(self):
  s={'ui_texts':[],'buttons':[dict(panel='gift',row_id='7',role='lock',text='toggle',interactable=False,input_verified=False)]}
  with self.assertRaises(ValueError):resolve(s,'gift:7:lock')
if __name__=='__main__':unittest.main()
