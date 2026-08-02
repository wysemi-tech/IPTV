import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build import aggregate, decode_payload, parse_m3u, render
import build as playlist_builder


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
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                request_path = self.path.split("?", 1)[0]
                if request_path == "/source.m3u":
                    body = (
                        "#EXTM3U\n#EXTINF:-1,CCTV1\n"
                        "http://127.0.0.1:{}/live.m3u8\n"
                    ).format(self.server.server_port).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                responses = {
                    "/live.m3u8": (
                        "application/vnd.apple.mpegurl",
                        b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n/seg1.ts\n#EXTINF:4,\n/seg2.ts\n",
                    ),
                    "/vod.m3u8": (
                        "application/vnd.apple.mpegurl",
                        b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n/seg1.ts\n#EXTINF:4,\n/seg2.ts\n#EXT-X-ENDLIST\n",
                    ),
                    "/master.m3u8": (
                        "application/vnd.apple.mpegurl",
                        b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360\n/low.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\n/hd.m3u8\n",
                    ),
                    "/low.m3u8": (
                        "application/vnd.apple.mpegurl",
                        b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n/seg1.ts\n#EXTINF:4,\n/seg2.ts\n",
                    ),
                    "/hd.m3u8": (
                        "application/vnd.apple.mpegurl",
                        b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n/seg1.ts\n#EXTINF:4,\n/seg2.ts\n",
                    ),
                    "/slow.m3u8": (
                        "application/vnd.apple.mpegurl",
                        b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n/slow1.ts\n#EXTINF:4,\n/slow2.ts\n",
                    ),
                    "/rolling.m3u8": (
                        "application/vnd.apple.mpegurl",
                        b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n/expired1.ts\n#EXTINF:4,\n/expired2.ts\n#EXTINF:4,\n/seg1.ts\n#EXTINF:4,\n/seg2.ts\n",
                    ),
                    "/seg1.ts": ("video/mp2t", b"A" * 32768),
                    "/seg2.ts": ("video/mp2t", b"B" * 32768),
                    "/slow1.ts": ("video/mp2t", b"S" * 512),
                    "/slow2.ts": ("video/mp2t", b"T" * 512),
                }
                if request_path not in responses:
                    self.send_response(404)
                    self.end_headers()
                    return
                content_type, body = responses[request_path]
                if request_path.startswith("/slow") and request_path.endswith(".ts"):
                    time.sleep(0.05)
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = "http://127.0.0.1:{}".format(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def test_live_hls_with_consecutive_segments_is_accepted(self):
        result = playlist_builder.probe_stream(self.base_url + "/live.m3u8", timeout=2)
        self.assertTrue(result.ok)

    def test_vod_playlist_is_rejected(self):
        result = playlist_builder.probe_stream(self.base_url + "/vod.m3u8", timeout=2)
        self.assertFalse(result.ok)

    def test_master_playlist_uses_highest_quality_variant(self):
        result = playlist_builder.probe_stream(self.base_url + "/master.m3u8", timeout=2)
        self.assertEqual((True, "1920x1080"), (result.ok, result.resolution))

    def test_stream_below_minimum_download_speed_is_rejected(self):
        result = playlist_builder.probe_stream(
            self.base_url + "/slow.m3u8", timeout=2, min_speed_kbps=1000
        )
        self.assertFalse(result.ok)

    def test_live_probe_uses_newest_media_segments(self):
        result = playlist_builder.probe_stream(self.base_url + "/rolling.m3u8", timeout=2)
        self.assertTrue(result.ok)

    def test_expiring_signed_url_is_rejected(self):
        result = playlist_builder.probe_stream(
            self.base_url + "/live.m3u8?auth_key=1999999999-secret", timeout=2
        )
        self.assertFalse(result.ok)

    def test_best_three_backups_use_distinct_hosts(self):
        candidates = [
            playlist_builder.VerifiedEntry(
                playlist_builder.Entry("CCTV-1", "https://a.example/slow.m3u8"),
                playlist_builder.ProbeResult(True, "https://a.example/slow.m3u8", 200, 8000, "1920x1080"),
            ),
            playlist_builder.VerifiedEntry(
                playlist_builder.Entry("CCTV1 高清", "https://a.example/fast.m3u8"),
                playlist_builder.ProbeResult(True, "https://a.example/fast.m3u8", 180, 12000, "1920x1080"),
            ),
            playlist_builder.VerifiedEntry(
                playlist_builder.Entry("CCTV-1 综合", "https://b.example/live.m3u8"),
                playlist_builder.ProbeResult(True, "https://b.example/live.m3u8", 90, 15000, "1280x720"),
            ),
            playlist_builder.VerifiedEntry(
                playlist_builder.Entry("CCTV1", "https://c.example/live.m3u8"),
                playlist_builder.ProbeResult(True, "https://c.example/live.m3u8", 110, 10000, "1920x1080"),
            ),
            playlist_builder.VerifiedEntry(
                playlist_builder.Entry("CCTV1", "https://d.example/live.m3u8"),
                playlist_builder.ProbeResult(True, "https://d.example/live.m3u8", 100, 5000, "3840x2160"),
            ),
        ]
        selected = playlist_builder.select_verified(candidates, per_channel=3)
        self.assertEqual(
            ["b.example", "a.example", "c.example"],
            [playlist_builder.urlsplit(item.entry.url).hostname for item in selected],
        )

    def test_build_keeps_previous_playlist_when_health_collapses(self):
        previous = playlist_builder.render(
            [
                playlist_builder.Entry("频道{}".format(index), "https://old{}.example/live.m3u8".format(index))
                for index in range(4)
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources.json"
            output = root / "china.m3u8"
            sources.write_text(
                json.dumps({"sources": [{"name": "fixture", "url": self.base_url + "/source.m3u"}]}),
                encoding="utf-8",
            )
            output.write_text(previous, encoding="utf-8")
            with self.assertRaises(RuntimeError):
                playlist_builder.build(
                    sources,
                    output,
                    timeout=2,
                    workers=2,
                    per_channel=3,
                    min_retention_ratio=0.75,
                )
            self.assertEqual(previous, output.read_text(encoding="utf-8"))

    def test_same_stream_with_conflicting_channel_names_is_rejected(self):
        candidates = [
            playlist_builder.VerifiedEntry(
                playlist_builder.Entry("甲频道", "http://shared.example/live.m3u8"),
                playlist_builder.ProbeResult(True, "http://shared.example/live.m3u8", 50, 5000),
            ),
            playlist_builder.VerifiedEntry(
                playlist_builder.Entry("乙频道", "https://shared.example/live.m3u8"),
                playlist_builder.ProbeResult(True, "https://shared.example/live.m3u8", 50, 5000),
            ),
        ]
        self.assertEqual([], playlist_builder.select_verified(candidates))

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
