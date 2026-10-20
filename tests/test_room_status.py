import unittest
from robotomy.live import _hazards,observation_diff,observation_sections

class RoomStatusTests(unittest.TestCase):
    def test_click_coordinates_are_separate_verified_and_retracted(self):
        room={'room_id':'1','x':10,'y':20,'click':{'x':70,'y':80,'target_id':'2','input_verified':True,'secret':99}}
        def read():return _hazards({'room_status':[room]},{'width':100,'height':100})['room_status'][0]
        self.assertEqual(read()['click'],{'x':70,'y':80,'target_id':'2','input_verified':True})
        room['click']['x']=101
        with self.assertRaises(ValueError):read()
        room['click']=None;self.assertIsNone(read()['click'])
        room['click']={'x':1,'y':2,'target_id':'2','input_verified':False}
        with self.assertRaises(ValueError):read()
    def test_room_fields_and_display_unknown(self):
        room={'room_id':'display1','room_label':'shown name','x':10,'y':20,
              'qliphoth_counter':{'display':'number','value':2},
              'work_boxes':{'pe_boxes':3,'ne_boxes':2,'generated_total':999},
              'stored_pe_boxes':42,'work_penalty_text':'-12%','secret':'not exported'}
        result=_hazards({'room_status':[room]}, {'width':100,'height':100})['room_status'][0]
        self.assertEqual(result['work_boxes']['generated_total'],5)
        self.assertEqual(result['stored_pe_boxes'],42);self.assertNotIn('secret',result)
        room['qliphoth_counter']={'display':'unknown','value':999}
        self.assertIsNone(_hazards({'room_status':[room]},None)['room_status'][0]['qliphoth_counter']['value'])
    def test_cost_wording_and_absence(self):
        m={'stored_pe_text':'42','costs':[{'kind':'weapon_cost_or_stock','label':'displayed item',
            'display_text':'비용 30','x':10,'y':20}]}
        self.assertEqual(_hazards({'creature_management':m},None)['creature_management'],{**m,'details':[]})
        self.assertEqual(_hazards({},None)['room_status'],[])
        self.assertIsNone(_hazards({},None)['creature_management'])
    def test_changes_prioritized_and_closure_retracted(self):
        s={'captured_at_utc':'2026-10-19T00:00:00+00:00','console':{'hazards':{'room_status':[{'room_id':'x'}]}}}
        old={'id':'a','identity':'x','selection':{},'sections':observation_sections(s),'captured_at_utc':s['captured_at_utc']}
        current={**s,'console':{'hazards':{'room_status':[]}}}
        d=observation_diff(old,current,'b',{},'x')
        self.assertEqual(d['priority_changes']['room_status'],[])
    def test_invalid_coordinates_rejected(self):
        with self.assertRaises(ValueError):
            _hazards({'room_status':[{'room_id':'x','x':101,'y':0}]},{'width':100,'height':100})
    def test_management_details_are_labeled_and_whitelisted(self):
        m={'details':[{'kind':'work_damage','type':'WHITE','range':'1-2','hidden_model':99},
                      {'kind':'work_result_pe_range','label':'좋음','range':'8-10'},
                      {'kind':'ego_suit_resistance','type_and_factor':'RED (0.9)','resistance':'견딤'}]}
        details=_hazards({'creature_management':m},None)['creature_management']['details']
        self.assertNotIn('hidden_model',details[0]);self.assertEqual(details[1]['kind'],'work_result_pe_range')

    def test_unlock_reasons_remain_independent(self):
        def read(balance,cost,prerequisite='not_indicated'):
            return _hazards({'creature_management':{'stored_pe_text':balance,'costs':[
                {'kind':'unlock','label':'관리법','display_text':cost,'x':1,'y':2,'prerequisite':prerequisite}]}},None)['creature_management']['costs'][0]
        self.assertEqual(read('4','5')['funds'],'insufficient')
        item=read('12','5','required');self.assertEqual(item['funds'],'sufficient');self.assertEqual(item['prerequisite'],'required')
        self.assertEqual(read('1','5','required')['prerequisite'],'required')
        self.assertEqual(read(None,'5')['funds'],'unknown')
        self.assertEqual(read('12','?')['funds'],'unknown')
        self.assertEqual(read('12','5')['prerequisite'],'not_indicated')
    def test_preference_groups_preserve_missing_levels(self):
        d={'kind':'work_preference','work':'본능 작업','I':'보통','III':'낮음','hidden_probability':0.2}
        out=_hazards({'creature_management':{'details':[d]}},None)['creature_management']['details'][0]
        self.assertEqual(out,{'kind':'work_preference','work':'본능 작업','I':'보통','III':'낮음'})
