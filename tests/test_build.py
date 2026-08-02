import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build import aggregate, decode_payload, parse_m3u, render


SAMPLE = """#EXTM3U
#EXTINF:-1 tvg-id="cctv1" group-title="央视频道",CCTV-1 综合 HD
https://example.com/cctv1.m3u8
#EXTINF:-1 group-title="卫视",湖南卫视
https://example.com/hunan.m3u8
#EXTINF:-1 tvg-country="HK",凤凰中文
https://example.com/phoenix.m3u8
#EXTINF:-1 group-title="购物",快乐购物
https://example.com/shop.m3u8
#EXTINF:-1 tvg-country="CN",NHK World
https://example.com/nhk.m3u8
#EXTINF:-1 tvg-country="CN",J2
https://example.com/j2.m3u8
"""


class BuildTests(unittest.TestCase):
    def test_parse(self):
        entries = parse_m3u(SAMPLE)
        self.assertEqual(6, len(entries))
        self.assertEqual("CCTV-1 综合 HD", entries[0].name)

    def test_filter_group_and_render(self):
        entries = aggregate([SAMPLE, SAMPLE])
        self.assertEqual(2, len(entries))
        output = render(entries)
        self.assertEqual(1, output.count("https://example.com/cctv1.m3u8"))
        self.assertIn('group-title="央视"', output)
        self.assertIn('group-title="卫视"', output)
        self.assertNotIn("凤凰", output)
        self.assertNotIn("购物", output)
        self.assertNotIn("NHK", output)
        self.assertNotIn(",J2", output)

    def test_gb18030_decode(self):
        self.assertEqual("湖南卫视", decode_payload("湖南卫视".encode("gb18030")))


if __name__ == "__main__":
    unittest.main()
