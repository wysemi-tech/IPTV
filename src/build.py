#!/usr/bin/env python3
"""Build a mainland-China-only Extended M3U playlist."""

import argparse
import json
import math
import re
import sys
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urljoin, urlsplit


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

EXPIRING_QUERY_KEYS = {
    "auth_key", "expires", "expire", "expiration", "sign", "signature",
    "token", "txsecret", "txtime", "user_session_id",
}


@dataclass(frozen=True)
class Entry:
    name: str
    url: str
    attrs: Tuple[Tuple[str, str], ...] = ()

    def attr_dict(self) -> Dict[str, str]:
        return dict(self.attrs)


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    final_url: str
    latency_ms: int = 0
    speed_kbps: int = 0
    resolution: str = ""
    reason: str = ""


@dataclass(frozen=True)
class VerifiedEntry:
    entry: Entry
    probe: ProbeResult


def _get_bytes(url: str, timeout: int, limit: int = 512 * 1024) -> Tuple[bytes, str, float]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(limit)
        final_url = response.geturl()
    return body, final_url, max(time.monotonic() - started, 0.001)


def probe_stream(url: str, timeout: int = 8, min_speed_kbps: int = 1000) -> ProbeResult:
    query_keys = {key.casefold() for key, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True)}
    if query_keys & EXPIRING_QUERY_KEYS:
        return ProbeResult(False, url, reason="包含临时签名参数")
    try:
        payload, final_url, playlist_seconds = _get_bytes(url, timeout)
        text = decode_payload(payload)
        if not text.lstrip().startswith("#EXTM3U"):
            return ProbeResult(False, final_url, reason="不是 HLS 播放列表")
        resolution = ""
        if "#EXT-X-STREAM-INF:" in text:
            lines = [line.strip() for line in text.replace("\r", "").split("\n")]
            variants = []
            for index, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF:"):
                    continue
                target = next(
                    (candidate for candidate in lines[index + 1:] if candidate and not candidate.startswith("#")),
                    "",
                )
                match = re.search(r"RESOLUTION=(\d+x\d+)", line, re.I)
                size = match.group(1).lower() if match else ""
                pixels = 0
                if size:
                    width, height = (int(value) for value in size.split("x", 1))
                    pixels = width * height
                bandwidth_match = re.search(r"BANDWIDTH=(\d+)", line, re.I)
                bandwidth = int(bandwidth_match.group(1)) if bandwidth_match else 0
                if target:
                    variants.append((pixels, bandwidth, size, target))
            if not variants:
                return ProbeResult(False, final_url, reason="主播放列表没有变体")
            _, _, resolution, variant_path = max(variants)
            payload, final_url, _ = _get_bytes(urljoin(final_url, variant_path), timeout)
            text = decode_payload(payload)
            if not text.lstrip().startswith("#EXTM3U"):
                return ProbeResult(False, final_url, reason="变体不是 HLS 播放列表")
        if "#EXT-X-ENDLIST" in text:
            return ProbeResult(False, final_url, reason="点播或已结束的播放列表")
        segment_paths = [
            line.strip()
            for line in text.replace("\r", "").split("\n")
            if line.strip() and not line.lstrip().startswith("#")
        ][-2:]
        if len(segment_paths) < 2:
            return ProbeResult(False, final_url, reason="媒体分片不足")
        downloaded = 0
        segment_seconds = 0.0
        for segment_path in segment_paths:
            segment, _, elapsed = _get_bytes(urljoin(final_url, segment_path), timeout)
            if not segment:
                return ProbeResult(False, final_url, reason="媒体分片为空")
            downloaded += len(segment)
            segment_seconds += elapsed
        speed_kbps = round(downloaded * 8 / max(segment_seconds, 0.001) / 1000)
        if speed_kbps < min_speed_kbps:
            return ProbeResult(
                False,
                final_url,
                latency_ms=round(playlist_seconds * 1000),
                speed_kbps=speed_kbps,
                resolution=resolution,
                reason="下载速率低于 {} kbps".format(min_speed_kbps),
            )
        return ProbeResult(
            True,
            final_url,
            latency_ms=round(playlist_seconds * 1000),
            speed_kbps=speed_kbps,
            resolution=resolution,
        )
    except Exception as error:
        return ProbeResult(False, url, reason=str(error))


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


def channel_key(name: str) -> str:
    normalized = normalized_name(name)
    cctv = re.search(r"cctv(\d+\+?)", normalized)
    return "cctv" + cctv.group(1) if cctv else normalized


def _resolution_pixels(resolution: str) -> int:
    match = re.fullmatch(r"(\d+)x(\d+)", resolution)
    return int(match.group(1)) * int(match.group(2)) if match else 0


def _stream_identity(url: str) -> Tuple[str, Optional[int], str, str]:
    parsed = urlsplit(url)
    port = parsed.port
    if (parsed.scheme.casefold(), port) in {("http", 80), ("https", 443)}:
        port = None
    return ((parsed.hostname or "").casefold(), port, parsed.path, parsed.query)


def select_verified(candidates: Iterable[VerifiedEntry], per_channel: int = 3) -> List[VerifiedEntry]:
    candidate_list = [candidate for candidate in candidates if candidate.probe.ok]
    identity_channels: Dict[Tuple[str, Optional[int], str, str], set] = {}
    for candidate in candidate_list:
        identity = _stream_identity(candidate.probe.final_url)
        identity_channels.setdefault(identity, set()).add(channel_key(candidate.entry.name))
    conflicting = {identity for identity, channels in identity_channels.items() if len(channels) > 1}

    grouped: Dict[str, List[VerifiedEntry]] = {}
    for candidate in candidate_list:
        if _stream_identity(candidate.probe.final_url) not in conflicting:
            grouped.setdefault(channel_key(candidate.entry.name), []).append(candidate)

    selected: List[VerifiedEntry] = []
    for key in sorted(grouped):
        ranked = sorted(
            grouped[key],
            key=lambda item: (
                -item.probe.speed_kbps,
                -_resolution_pixels(item.probe.resolution),
                item.probe.latency_ms,
                item.entry.url,
            ),
        )
        hosts = set()
        for candidate in ranked:
            host = (urlsplit(candidate.entry.url).hostname or "").casefold()
            if not host or host in hosts:
                continue
            hosts.add(host)
            selected.append(candidate)
            if len(hosts) >= per_channel:
                break
    return selected


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


def _probe_candidates(
    entries: Sequence[Entry], timeout: int, workers: int, candidate_limit: int,
    min_speed_kbps: int,
) -> List[VerifiedEntry]:
    candidates: List[Entry] = []
    counts: Dict[str, int] = {}
    for entry in entries:
        if not entry.url.casefold().startswith(("http://", "https://")):
            continue
        key = channel_key(entry.name)
        if counts.get(key, 0) >= candidate_limit:
            continue
        counts[key] = counts.get(key, 0) + 1
        candidates.append(entry)

    verified: List[VerifiedEntry] = []
    failures = Counter()
    print("[CHECK] 开始验证 {} 个候选".format(len(candidates)), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(probe_stream, entry.url, timeout, min_speed_kbps): entry
            for entry in candidates
        }
        for future in as_completed(futures):
            entry = futures[future]
            result = future.result()
            if result.ok:
                verified.append(VerifiedEntry(entry, result))
            else:
                failures[result.reason or "未知错误"] += 1
    print(
        "[CHECK] {} 个候选，{} 个通过连续分片验证".format(len(candidates), len(verified)),
        flush=True,
    )
    if failures:
        summary = "; ".join(
            "{}: {}".format(reason, count) for reason, count in failures.most_common(8)
        )
        print("[CHECK] 主要失败原因: {}".format(summary), flush=True)
    return verified


def _entry_with_quality(verified: VerifiedEntry) -> Entry:
    attrs = verified.entry.attr_dict()
    attrs["x-latency-ms"] = str(verified.probe.latency_ms)
    attrs["x-speed-kbps"] = str(verified.probe.speed_kbps)
    if verified.probe.resolution:
        attrs["x-resolution"] = verified.probe.resolution
    return Entry(verified.entry.name, verified.entry.url, tuple(sorted(attrs.items())))


def _channel_count(text: str) -> int:
    return len({channel_key(entry.name) for entry in parse_m3u(text)})


def load_sources(path: Path) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [source for source in data["sources"] if source.get("enabled", True)]


def build(
    source_file: Path,
    output: Path,
    timeout: int = 5,
    workers: int = 48,
    per_channel: int = 3,
    candidate_limit: int = 4,
    min_retention_ratio: float = 0.5,
    min_speed_kbps: int = 1000,
) -> int:
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
    verified = _probe_candidates(entries, timeout, workers, candidate_limit, min_speed_kbps)
    selected = select_verified(verified, per_channel=per_channel)
    if not selected:
        raise RuntimeError("没有直播源通过连续媒体分片验证")
    rendered_entries = [_entry_with_quality(item) for item in selected]
    new_text = render(rendered_entries)

    if output.exists() and min_retention_ratio > 0:
        previous_text = output.read_text(encoding="utf-8")
        previous_channels = _channel_count(previous_text)
        current_channels = _channel_count(new_text)
        minimum = math.ceil(previous_channels * min_retention_ratio)
        if previous_channels and current_channels < minimum:
            raise RuntimeError(
                "健康频道从 {} 降至 {}，低于安全阈值 {}，保留上一版订阅".format(
                    previous_channels, current_channels, minimum
                )
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(new_text)
    temporary.replace(output)
    print(
        "[DONE] {}: {} 个频道，{} 条优质线路".format(
            output, _channel_count(new_text), len(rendered_entries)
        )
    )
    if failures:
        print("[INFO] {} 个上游暂时失败，已使用其余上游生成".format(len(failures)))
    return len(rendered_entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("sources.json"))
    parser.add_argument("--output", type=Path, default=Path("dist/china.m3u8"))
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument("--per-channel", type=int, default=3)
    parser.add_argument("--candidate-limit", type=int, default=4)
    parser.add_argument("--min-speed-kbps", type=int, default=1000)
    parser.add_argument("--min-retention-ratio", type=float, default=0.5)
    parser.add_argument(
        "--force",
        action="store_true",
        help="忽略上一版健康频道数量安全阈值",
    )
    args = parser.parse_args()
    build(
        args.sources,
        args.output,
        timeout=args.timeout,
        workers=args.workers,
        per_channel=args.per_channel,
        candidate_limit=args.candidate_limit,
        min_retention_ratio=0 if args.force else args.min_retention_ratio,
        min_speed_kbps=args.min_speed_kbps,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
