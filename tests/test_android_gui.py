#!/usr/bin/env python3
"""Pure stdlib framebuffer tests: Android blank PNG must not claim GUI success."""
import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[1]
GUI=ROOT/"profiles/android-arm64/scripts/inspect-gui.py"
spec=importlib.util.spec_from_file_location("android_gui_inspection",GUI)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def make_rgba_png(w,h,rgb=(0,0,0),filtertype=0):
    def chunk(tag,data):
        return struct.pack(">I",len(data))+tag+data+struct.pack(">I",zlib.crc32(tag+data)&0xffffffff)
    rows=[]
    for y in range(h):
        row=bytearray()
        for x in range(w):
            row.extend((*rgb,255))
        if filtertype==1: # Sub filter
            encoded=bytearray(row)
            for i in range(len(row)-1,-1,-1):
                encoded[i]=(row[i]-(row[i-4] if i>=4 else 0))&255
            row=encoded
        rows.append(bytes([filtertype])+row)
    return (m.PNG+chunk(b"IHDR",struct.pack(">IIBBBBB",w,h,8,6,0,0,0))
            +chunk(b"IDAT",zlib.compress(b"".join(rows)))
            +chunk(b"IEND",b""))

class AndroidGuiProofTests(unittest.TestCase):
    def test_actual_launcher_evidence_requires_real_home_and_rendered_pixels(self):
        observed=[
          {"check":"boot_completed","exit":0,"stdout":"1"},
          {"check":"surfaceflinger","exit":0,"stdout":"Service SurfaceFlinger: found"},
          {"check":"display","exit":0,"stdout":"Physical size: 320x480"},
          {"check":"launcher_resolution","exit":0,"stdout":"com.android.launcher3/.Launcher"},
          {"check":"home_launch","exit":0,"stdout":"Starting: Intent { act=android.intent.action.MAIN }"},
        ]
        stats={"all_black":False,"visible_pixels":153600,"distinct_sample_colors":100}
        self.assertEqual(m.classify_gui(observed,stats),"LAUNCHER_HOME_EVIDENCE")
        bad=[dict(x) for x in observed]
        bad[3]["stdout"]="com.android.settings/.FallbackHome"
        self.assertEqual(m.classify_gui(bad,stats),"VISIBLE_FRAMEBUFFER_NOT_PROVEN_LAUNCHER")
        empty=dict(stats,all_black=True,visible_pixels=0,distinct_sample_colors=1)
        self.assertEqual(m.classify_gui(observed,empty),"VISIBLE_FRAMEBUFFER_NOT_PROVEN_LAUNCHER")

    def test_black_screen_is_not_launcher_proof(self):
        png=make_rgba_png(320,480)
        data=m.inspect_png(png)
        self.assertTrue(data["all_black"])
        self.assertEqual(data["visible_pixels"],0)
        self.assertEqual((data["width"],data["height"]),(320,480))
    def test_nonblack_framebuffer_is_detected(self):
        png=make_rgba_png(12,9,(37,96,42))
        data=m.inspect_png(png)
        self.assertFalse(data["all_black"])
        self.assertEqual(data["visible_pixels"],108)
    def test_subfiltered_framebuffer_decode(self):
        png=make_rgba_png(5,3,(1,2,3),filtertype=1)
        self.assertEqual(m.inspect_png(png)["visible_pixels"],15)
    def test_refuse_non_png_and_unsupported_layout(self):
        with self.assertRaises(ValueError):
            m.inspect_png(b"not a png")
        bad=make_rgba_png(4,4)
        bad=bad[:16]+struct.pack(">I",9000)+bad[20:]
        with self.assertRaises(ValueError):
            m.inspect_png(bad)

if __name__=="__main__":
    unittest.main()
