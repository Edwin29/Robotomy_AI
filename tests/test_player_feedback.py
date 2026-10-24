import copy
import tempfile
import unittest
from pathlib import Path
from robotomy.live import _ui_items, command_rows
from robotomy.perception import Delivery, project
from robotomy.quick_input import remember, movement_orders as observe
from robotomy.quick_input import targets

def sample():
    return dict(process_id=1,scene='Main',screen=dict(width=1280,height=720),
                captured_at_utc='2026-10-20T00:00:00Z',sequence=1,ui_texts=[],buttons=[],
                console=dict(session='a'*32,motion=dict(status='available',tracks=[])))

def text(panel,row,role,value):
    return dict(panel=panel,row_id=row,role=role,text=value,x=10,y=10,width=100,height=20)

class PlayerFeedbackTests(unittest.TestCase):
    def test_enemy_is_not_employee_row(self):
        s=sample()
        s['ui_texts']=_ui_items([text('command','selected_enemy','name','적'),
            text('command','selected_enemy','factor_red','0.5'),
            text('enemy','selected','attack_red','red')],512)
        self.assertEqual(command_rows(s),[])
        self.assertEqual(project(s)['selected_enemy'],dict(name='적',factor_red='0.5',attack_types=['red']))

    def test_story_state_and_modal_actions(self):
        s=sample();s['ui_texts']=_ui_items([text('screen','current','base','story'),
            text('story','a','display_state','revealing')],512)
        self.assertEqual(project(s)['screen_context']['story_state'],'revealing')
        s['ui_texts'][1]['text']='ready'
        self.assertEqual(project(s)['screen_context']['story_state'],'ready')
        s['buttons']=[dict(text('story','choice','choice','선택'),target_id='42',
                           hit_x=50,hit_y=20,input_verified=True,interactable=True)]
        p=project(s)
        self.assertEqual(p['screen_context']['story_state'],'choice')
        self.assertEqual(p['screen_context']['actions'][0]['ref'],'button:42')

    def test_selection_priority_and_no_hover_selection(self):
        s=sample();s['ui_texts']=[text('selection','panel','displayed_name','Hover')]
        self.assertEqual(project(s)['selection']['employees_in_view'],[])
        d=Delivery();d.offer(s);s['ui_texts'][0]['text']='Other';s['sequence']+=1
        out=d.offer(s)
        self.assertTrue(any(x.get('set',[None])[0]=='selection' for x in out['priority_changes']))

    def test_entity_removal_does_not_claim_kill(self):
        s=sample()
        v=dict(x=0,y=0)
        t=dict(track_id='b'*32,entity_id='c'*32,entity=dict(kind='creature',name='적',click=dict(x=10,y=10)),
            position=dict(x=10,y=10),bounds={},state='tracking',screen_velocity=v,object_velocity=v,camera_velocity=v)
        s['console']['motion']['tracks']=[t]
        self.assertEqual(targets(s)[0]['ref'],'entity:'+'b'*32)
        d=Delivery();d.offer(s);s['console']['motion']['tracks']=[];s['sequence']+=1
        self.assertEqual(d.offer(s)['entity_visibility_changes'][0]['outcome'],'unconfirmed')

    def test_orders_are_command_memory_not_internal_destination(self):
        s=sample();v=dict(x=0,y=0)
        t=dict(track_id='b'*32,entity_id='c'*32,employee=dict(name='A',selected=True,status='idle'),
            position=dict(x=10,y=10),state='tracking',object_velocity=v,screen_velocity=v,camera_velocity=v)
        s['console']['motion']['tracks']=[t]
        with tempfile.TemporaryDirectory() as root:
            remember(Path(root),s,'employee:'+'b'*32,'main_room:1:2',123)
            order=observe(Path(root),s)['c'*32]
            self.assertEqual(order['observed_status'],'not_yet_confirmed')
            self.assertEqual(order['basis'],'player_command')
            t['employee']['status']='moving'
            self.assertEqual(observe(Path(root),s)['c'*32]['observed_status'],'moving')
            s['console']['session']='d'*32
            self.assertEqual(observe(Path(root),s),{})

if __name__=='__main__':unittest.main()
