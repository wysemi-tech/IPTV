# 中国大陆 IPTV 聚合订阅

自动聚合公开直播列表，只保留中国大陆频道，输出标准 Extended M3U 播放列表：

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
- 聚合多个公开上游，按播放地址去重
- 自动识别 UTF-8、GB18030 和 Big5 编码
- 自动归类为央视、卫视和地方台
- 单个上游故障时继续使用其余源生成
- GitHub Actions 每日自动更新，也支持手动运行

## 本地生成

只依赖 Python 3.8+ 标准库：

```bash
python src/build.py
python -m unittest discover -s tests -v
```

上游列表在 `sources.json`。`iptv-org` 的 CN 分类可能包含境外中文频道，因此默认关闭；如自行启用，请复核生成结果。新增来源时请确认其内容仅用于个人学习与测试，并尊重频道、平台和当地法律规定。

## 说明

本项目不存储或转码任何视频，只整理第三方公开播放地址。直播源具有地域、运营商和时效限制；能被收录不代表在所有网络均可播放。若权利人要求移除某个公开地址，请提交 Issue。

参考项目：[imDazui/Tvlist-awesome-m3u-m3u8](https://github.com/imDazui/Tvlist-awesome-m3u-m3u8)。
