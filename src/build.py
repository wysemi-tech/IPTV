#!/usr/bin/env python3
"""Build a mainland-China-only Extended M3U playlist."""

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


USER_AGENT = "China-IPTV-Aggregator/1.0 (+https://github.com/)"
ATTRIBUTE_RE = re.compile(r'([\w-]+)="([^"]*)"')
SPACE_RE = re.compile(r"\s+")

# Mainland-only means Hong Kong, Macao, Taiwan, overseas and adult channels are
# intentionally excluded. Shopping and test channels are omitted for usability.
BLOCKED_TEXT = (
    "香港", "澳门", "澳門", "台湾", "台灣", "凤凰", "鳳凰", "翡翠", "明珠",
    "tvb", "viutv", "rthk", "hktv", "澳门", "macao", "macau", "taiwan",
    "hong kong", "adult", "xxx", "成人", "购物", "購物", "导购", "測試", "测试",
    "韩国", "日本", "美国", "英国", "法国", "德国", "俄罗斯", "海外",
    "nhk", "abn china", "angel tv", "ando tv", "tv brics",
)

BLOCKED_NAMES = {"j2", "cna", "home plus"}

GROUP_ORDER = {
    "央视": 0,
    "卫视": 1,
    "地方台": 2,
    "其他": 3,
}


@dataclass(frozen=True)
class Entry:
    name: str
    url: str
    attrs: Tuple[Tuple[str, str], ...] = ()

    def attr_dict(self) -> Dict[str, str]:
        return dict(self.attrs)


def decode_payload(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "big5"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            pass
    return payload.decode("utf-8", errors="replace")


def fetch(url: str, timeout: int = 25) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return decode_payload(response.read())


def parse_extinf(line: str) -> Tuple[str, Dict[str, str]]:
    attrs = dict(ATTRIBUTE_RE.findall(line))
    name = line.rsplit(",", 1)[-1].strip() if "," in line else "未命名频道"
    return name or "未命名频道", attrs


def parse_m3u(text: str) -> List[Entry]:
    entries: List[Entry] = []
    pending: Optional[Tuple[str, Dict[str, str]]] = None
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        if line.upper().startswith("#EXTINF:"):
            pending = parse_extinf(line)
            continue
        if line.startswith("#"):
            continue
        if pending and re.match(r"^(?:https?|rtsp|rtmp|udp|rtp)://", line, re.I):
            name, attrs = pending
            entries.append(Entry(name=name, url=line, attrs=tuple(sorted(attrs.items()))))
        pending = None
    return entries


def normalized_name(name: str) -> str:
    value = name.casefold().replace("中央电视台", "cctv").replace("央视", "cctv")
    value = re.sub(r"(?:高清|超清|蓝光|标清|频道|台|hd|fhd|uhd|4k|8k)", "", value)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)


def is_mainland(entry: Entry) -> bool:
    attrs = entry.attr_dict()
    haystack = " ".join((entry.name, attrs.get("group-title", ""), attrs.get("tvg-country", ""))).casefold()
    if any(keyword.casefold() in haystack for keyword in BLOCKED_TEXT):
        return False
    if entry.name.strip().casefold() in BLOCKED_NAMES:
        return False
    country = attrs.get("tvg-country", "").strip().upper()
    if country and country not in {"CN", "CHN"}:
        return False
    return bool(entry.name.strip() and entry.url.strip())


def channel_group(name: str, original_group: str = "") -> str:
    folded = name.casefold()
    if re.search(r"(?:cctv|央视|中央)", folded):
        return "央视"
    if "卫视" in name:
        return "卫视"
    if original_group in {"央视", "卫视", "地方台"}:
        return original_group
    return "地方台"


def clean_name(name: str) -> str:
    return SPACE_RE.sub(" ", name).strip().replace('"', "'")


def aggregate(playlists: Iterable[str]) -> List[Entry]:
    result: List[Entry] = []
    seen_urls = set()
    seen_pairs = set()
    for playlist in playlists:
        for entry in parse_m3u(playlist):
            if not is_mainland(entry):
                continue
            attrs = entry.attr_dict()
            name = clean_name(entry.name)
            url = entry.url.strip()
            pair = (normalized_name(name), url)
            if url in seen_urls or pair in seen_pairs:
                continue
            seen_urls.add(url)
            seen_pairs.add(pair)
            group = channel_group(name, attrs.get("group-title", ""))
            kept = {
                key: value
                for key, value in attrs.items()
                if key in {"tvg-id", "tvg-name", "tvg-logo"} and value
            }
            kept["group-title"] = group
            result.append(Entry(name=name, url=url, attrs=tuple(sorted(kept.items()))))
    return sorted(
        result,
        key=lambda item: (
            GROUP_ORDER[channel_group(item.name, item.attr_dict().get("group-title", ""))],
            normalized_name(item.name),
            item.url,
        ),
    )


def render(entries: Sequence[Entry]) -> str:
    lines = ["#EXTM3U"]
    for entry in entries:
        attributes = " ".join(
            '{}="{}"'.format(key, value.replace('"', "'")) for key, value in entry.attrs
        )
        prefix = "#EXTINF:-1" + ((" " + attributes) if attributes else "")
        lines.extend(("{},{}".format(prefix, entry.name), entry.url))
    return "\n".join(lines) + "\n"


def load_sources(path: Path) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [source for source in data["sources"] if source.get("enabled", True)]


def build(source_file: Path, output: Path, timeout: int = 25) -> int:
    texts: List[str] = []
    failures: List[str] = []
    for source in load_sources(source_file):
        name, url = str(source["name"]), str(source["url"])
        try:
            text = fetch(url, timeout=timeout)
            count = len(parse_m3u(text))
            if count == 0:
                raise ValueError("没有找到频道")
            texts.append(text)
            print("[OK] {}: {} 个条目".format(name, count))
        except Exception as error:  # Continue when one upstream is temporarily down.
            failures.append("{}: {}".format(name, error))
            print("[WARN] {}: {}".format(name, error), file=sys.stderr)

    if not texts:
        raise RuntimeError("所有上游源均不可用")
    entries = aggregate(texts)
    if not entries:
        raise RuntimeError("过滤后没有可写入的中国大陆频道")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render(entries))
    temporary.replace(output)
    print("[DONE] {}: {} 个去重后的中国大陆直播条目".format(output, len(entries)))
    if failures:
        print("[INFO] {} 个上游暂时失败，已使用其余上游生成".format(len(failures)))
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("sources.json"))
    parser.add_argument("--output", type=Path, default=Path("dist/china.m3u8"))
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()
    build(args.sources, args.output, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
