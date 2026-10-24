import copy
import unittest
from robotomy.live import _motion
from robotomy.perception import Delivery
from test_realtime_v2 import sample


class EmployeeBarsTests(unittest.TestCase):
    def motion(self):
        return dict(version=1, basis="display_projection_v1", coordinates="top_left_pixels",
                    units="pixels_per_real_second", status="available", tracks=[
                        dict(track_id="a"*32, entity_id="b"*32, state="acquiring",
                             position=dict(x=10,y=10),bounds=dict(x=5,y=5,width=10,height=10),
                             interval_ms=0,screen_velocity=None,object_velocity=None,camera_velocity=None,
                             employee=dict(name="A",status="idle",click=None,
                                           hp_bar=dict(ratio=.5,filled_pixels=10,total_pixels=20),sp_bar=None))])

    def test_validator_preserves_zero_not_hidden_values(self):
        m=self.motion()
        m["tracks"][0]["employee"]["hp_bar"].update(ratio=0,filled_pixels=0)
        out=_motion(m,dict(width=100,height=100))["tracks"][0]["employee"]
        self.assertEqual(out["hp_bar"]["ratio"],0)
        self.assertIsNone(out["sp_bar"])
        m["tracks"][0]["employee"]["hp_bar"]["ratio"]=.5
        with self.assertRaises(ValueError):_motion(m,dict(width=100,height=100))

    def test_bar_change_priority_hidden_clear_and_offscreen_remove(self):
        s=sample();s["console"]["motion"]=self.motion()
        d=Delivery();first=d.offer(s)
        s=copy.deepcopy(s);s["sequence"]+=1
        s["console"]["motion"]["tracks"][0]["employee"]["hp_bar"]=None
        out=d.offer(s)
        self.assertEqual(out["base"],first["id"])
        self.assertTrue(any(x.get("set")==["employees","b"*32,"hp_bar"] and x["value"] is None for x in out["priority_changes"]))
        s["sequence"]+=1;s["console"]["motion"]["tracks"]=[]
        out=d.offer(s)
        self.assertIn({"remove":["employees","b"*32]},out["changes"])
