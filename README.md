# 中国大陆 IPTV 聚合订阅

自动聚合近期维护的公开候选列表，只保留中国大陆频道，并实际下载 HLS 播放列表及连续媒体分片后输出标准 Extended M3U：

```text
dist/china.m3u8
```

## 订阅地址

```text
https://raw.githubusercontent.com/wysemi-tech/IPTV/main/dist/china.m3u8
```

也可以使用 jsDelivr（有缓存，更新不会立即生效）：

```text
https://cdn.jsdelivr.net/gh/wysemi-tech/IPTV@main/dist/china.m3u8
```

将地址粘贴到支持 M3U 的播放器中即可，例如 APTV、TiviMate、VLC 或 Kodi。

## 特性

- 仅保留中国大陆频道，排除港澳台、海外、成人、购物和测试频道
- 聚合多个近期维护的候选上游，不再依赖单一旧静态列表
- 实际验证 HLS 主清单、直播清单和最新两个连续媒体分片
- 过滤超时、HTML 假链接、点播/短循环及临时签名地址
- 按下载速率、分辨率和延迟排序，每频道最多保留 3 个不同 Host
- 自动识别 UTF-8、GB18030 和 Big5 编码
- 自动归类为央视、卫视和地方台
- 单个上游故障时继续使用其余源生成
- 健康频道异常减少时保留上一版，避免空清单覆盖
- GitHub Actions 每 6 小时自动更新，也支持手动运行

## 本地生成

只依赖 Python 3.8+ 标准库：

```bash
python src/build.py --workers 48 --timeout 5 --candidate-limit 4 --min-speed-kbps 1000
python -m unittest discover -s tests -v
```

上游列表在 `sources.json`，来源评估见 `docs/source-research.md`。候选仓库不是频道权利人，也不能保证每条地址长期有效；新增来源时必须重新探测并尊重频道、平台和当地法律规定。

## 说明

本项目不存储或转码任何视频，只在构建网络中验证并整理第三方公开播放地址。直播源具有地域、运营商和时效限制；通过一次实测不代表在所有地区、运营商或时段均可播放。GitHub Actions 位于境外，其测速不能替代中国移动、联通、电信的境内多点监测。若权利人要求移除某个公开地址，请提交 Issue。

参考项目：[imDazui/Tvlist-awesome-m3u-m3u8](https://github.com/imDazui/Tvlist-awesome-m3u-m3u8)。
