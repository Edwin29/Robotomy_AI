import unittest
from robotomy.observer_window import aspect_size


class ObserverAspectTests(unittest.TestCase):
    def test_width_and_height_drags_both_enlarge_and_shrink(self):
        previous=(1280,720)
        self.assertEqual(aspect_size((1600,720),previous),(1600,900))
        self.assertEqual(aspect_size((1280,900),previous),(1600,900))
        self.assertEqual(aspect_size((960,720),previous),(960,540))
        self.assertEqual(aspect_size((1280,540),previous),(960,540))

    def test_monitor_bound_and_integer_aspect(self):
        self.assertEqual(aspect_size((3840,2160),(1280,720),(4000,2400)),(1920,1080))
        for current in [(1999,1100),(1400,900),(5000,3000),(1,1)]:
            width,height=aspect_size(current,(1280,720),(1902,1010))
            self.assertEqual(width*9,height*16)
            self.assertLessEqual(width,1902);self.assertLessEqual(height,1010)
            self.assertGreaterEqual(width,640);self.assertGreaterEqual(height,360)
