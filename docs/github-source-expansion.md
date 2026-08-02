# GitHub 国内直播候选源扩展调研

调研日期：2026-08-02（Asia/Shanghai）

## 结论

在排除项目已经使用或明确排除的 `vbskycn/iptv`、`Guovin/iptv-api`、`iptv-org/iptv`、`YueChan/Live`、`hujingguang/ChinaIPTV`、`suxuang/myIPTV`、`imDazui/Tvlist-awesome-m3u-m3u8` 后，建议把下列来源加入**候选发现池**，继续走本项目自己的大陆频道过滤、HLS 实播检测、分片连续性检测、测速、同频道去重和降级保护。公开仓库的“可用”“高清”“自动更新”均不能替代本项目从中国网络环境进行的复测。

优先级：

1. `CCSH/IPTV`：宽覆盖、自动采集且有定期测速，适合作为主要新增候选池。
2. `zwc456baby/iptv_alive`：每日从联通网络自动验活，适合作为独立的实测补充。
3. `Free-TV/IPTV`：数量少但筛选原则清晰，适合补充官方/公开免费频道。
4. `Kimentanm/aptv`：2026 年仍有人维护，适合低权重补漏，但需严格处理请求头、境外和点播污染。

## 推荐来源

### 1. CCSH/IPTV — 高优先级

- 仓库：[CCSH/IPTV](https://github.com/CCSH/IPTV)
- 直接下载：
  - 完整 M3U：[live.m3u](https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.m3u)
  - 精简 M3U（不含地方台）：[live_lite.m3u](https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live_lite.m3u)
- 网络属性：混合 IPv4、IPv6 和域名型 HTTP(S) 地址；代码会统一清理 `IPV4` / `IPV6` 等名称标记，但没有分别发布 v4/v6 清单，必须由本项目按 URL 主机再次识别。参见[生成代码的名称清理和输出逻辑](https://github.com/CCSH/IPTV/blob/main/main.py)。
- 自动化与更新时间：README 声明直播源每天北京时间 04:00 更新、黑白名单每周五自动测速更新，EPG 每 6 小时更新；仓库包含 Actions，调研时有 1,205 次提交。参见[更新计划](https://github.com/CCSH/IPTV#-%E8%87%AA%E5%8A%A8%E6%9B%B4%E6%96%B0%E8%AF%B4%E6%98%8E%E5%8C%97%E4%BA%AC%E6%97%B6%E9%97%B4)和[工作流目录](https://github.com/CCSH/IPTV/tree/main/.github/workflows)。
- 测试能力：维护自动黑名单、手工黑白名单及响应时间白名单；默认响应时间阈值为 2 秒。它更接近“URL 响应/黑名单筛选”，不能据此推断已连续下载 HLS 媒体分片，也不能推断真实码率、分辨率或频道内容正确。参见[黑白名单及阈值代码](https://github.com/CCSH/IPTV/blob/main/main.py#L1209-L1239)。
- 内容边界：完整清单包含央视、卫视、地方台，也明确存在“港澳台”“国际台”、电影、电视剧、NewTV、咪咕和网络轮播分类；直播平台另有独立的 `live_platforms.m3u`，不要导入该文件。参见[频道分类代码](https://github.com/CCSH/IPTV/blob/main/main.py#L1424-L1457)。未见专门的成人关键词审计，因此仍需本项目的境外、港澳台、成人、购物、点播/轮播过滤。
- 授权：仓库代码标注 [MIT License](https://github.com/CCSH/IPTV/blob/main/LICENSE)，但许可证只覆盖仓库作者的代码/编排，不证明第三方频道链接或节目内容获准再分发。README 同样声明内容来自第三方并不保证可用性。
- 推荐接入：导入 `live.m3u`，赋予中等来源权重；不要相信其分组即可直接发布。保留来源标签，经过两段最新媒体分片、最低速率、分辨率和频道名一致性验证后才进入结果。

### 2. zwc456baby/iptv_alive — 高优先级补充

- 仓库：[zwc456baby/iptv_alive](https://github.com/zwc456baby/iptv_alive)
- 直接下载：只使用已测试的 [live.txt](https://raw.githubusercontent.com/zwc456baby/iptv_alive/master/live.txt)。名义上的 [live.m3u](https://raw.githubusercontent.com/zwc456baby/iptv_alive/refs/heads/master/live.m3u) 在 2026-08-02 检查时只有 `#EXTM3U` 文件头，不能加入抓取配置。
- 网络属性：混合 IPv4/IPv6。README 明确称内部 IPv6 可用性较高；地址仍可能受省份和运营商限制。
- 自动化与更新时间：README 声明每天凌晨自动筛选并提交，仓库调研时有 892 次提交并包含检测脚本 [`check.js`](https://github.com/zwc456baby/iptv_alive/blob/master/check.js)。
- 测试能力：在联通网络进行自动可用性测试；维护者明确提醒，筛选时可用的地址可能在一天内过期，且在电信/移动网络的可用性会下降。参见[README 的检测范围和限制](https://github.com/zwc456baby/iptv_alive#readme)。因此应把它视为“联通视角近期可连”的候选信号，而不是全国可播保证。
- 内容边界：仓库描述同时提到直播源与 4K 点播源，推荐只读取 `live.m3u`，继续拒绝带 `#EXT-X-ENDLIST`、固定短清单和明显电影/剧集/轮播名称的条目。README 没有成人、港澳台或海外的明确排除承诺，必须再次做频道归属与内容分类。
- 授权：仓库页面未显示明确开源许可证；“收集自互联网、仅做个人测试研究”不是再分发授权。只能把其中 URL 当发现线索，公开发布前仍需核查流地址来源和权利人政策。
- 推荐接入：让解析器支持它的 `频道名,URL` TXT 格式，作为独立于现有来源的每日验活补充；来源权重低于明确官方直播端点，但高于没有任何验活的静态清单。

### 3. Free-TV/IPTV — 中优先级、低数量高约束补充

- 仓库：[Free-TV/IPTV](https://github.com/Free-TV/IPTV)
- 直接下载：[playlist.m3u8](https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8)。仓库没有单独的中国文件，接入时只读取 `tvg-country="CN"` 或 `group-title="China"` 的条目。
- 网络属性：中国段以域名型 HTTPS/HTTP HLS 为主，夹有 YouTube 直播页面；没有单独 IPv4/IPv6 标记。必须拒绝非直接流 URL，保留 HLS 候选后再由 DNS/连接结果判断网络栈。
- 自动化与更新时间：Actions 根据 `lists/*.md` 生成总播放列表；[提交记录](https://github.com/Free-TV/IPTV/commits/master/)显示 2026-07-07 仍有 `Update Playlist (GitHub Actions)` 及人工频道维护提交。
- 测试与质量原则：项目公开要求“质量优先于数量”、尽可能 HD、每频道一个 URL、只收免费且主流的频道，并要求新增/修订频道通过 PR 提交证据；但这仍是人工维护规则，不是持续 HLS 分片测速。参见[项目原则与 PR 规则](https://github.com/Free-TV/IPTV#philosophy)。
- 内容边界：项目明确不收成人、宗教专台和政党专台；中国段在 2026-08-02 可见央视、CETV 和 TV BRICS 等约 17 条，其中 CETV 地址指向 `centv.cn`，部分 CCTV 地址则来自第三方 `olelive.com`。参见[当日生成清单的 China 段](https://github.com/Free-TV/IPTV/blob/master/playlist.m3u8#L415-L448)。应排除 CCTV-4 美洲/亚洲、TV BRICS Chinese 等非“中国大陆国内电视直播”目标，并对第三方中转保持低信任。
- 授权：仓库首页未显示可识别的 SPDX 许可证，调研时也未能确认仓库级 LICENSE；其“只收免费频道”规则不等同于允许复制或再分发第三方节目流。
- 推荐接入：作为小型交叉验证来源，特别是 CETV 等公开机构地址；来源总权重可较高，但对 `olelive.com` 等第三方 Host 单独降权。

### 4. Kimentanm/aptv — 中低优先级人工补充

- 仓库：[Kimentanm/aptv](https://github.com/Kimentanm/aptv)
- 直接下载：[m3u/iptv.m3u](https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u)。
- 网络属性：IPv4/IPv6 混合；不少 IPv4 线路集中在同一个中转 IP，部分条目还依赖 M3U 内的自定义 `User-Agent` / `Referer` 请求头，播放器和本项目探测器未必支持。
- 自动化与更新时间：README 明确说测试源“随缘更新”，没有自动测速承诺；但[该播放列表的提交历史](https://github.com/Kimentanm/aptv/commits/master/m3u/iptv.m3u)显示 2026 年仍有人工维护，最近一次为 2026-06-11（6 月 10 日也有更新），满足“近期有人维护”，不满足“自动持续验活”。
- 内容边界：混有翡翠、凤凰、CGTN 等非大陆国内目标，也有历年春晚 MP4/HLS 等点播或归档内容。必须严格走大陆频道白名单、直播判定和境外过滤；不能导入整个清单。
- 授权：仓库页面未显示明确 LICENSE，README 还注明测试源禁止传播；因此只能把 URL 当低信任发现线索，不能把其清单原样再发布。
- 推荐接入：低权重补漏。只保留本项目能按所需请求头连续验证 HLS 分片的大陆直播；对共享中转 Host 限额，避免一个代理故障拖垮大量频道。

## 明确剔除的近似候选

以下项目本轮不建议加入候选池：

- [PizazzGY/TV](https://github.com/PizazzGY/TV)：是 `Guovin/iptv-api` 的 fork，README 也明确表示框架本身不提供数据源；属于现有上游的衍生运行实例，不增加独立发现价值。
- [TianmuTNT/iptv](https://github.com/TianmuTNT/iptv)：虽在 2026-07-29 仍自动更新，但其[抓取脚本](https://github.com/TianmuTNT/iptv/blob/main/get_iptv.py#L438-L446)只是合并 `zwc456baby/iptv_alive` 与已经使用的 `vbskycn/iptv`，并未做媒体分片验证，属于重复聚合。
- [zhi35/iptv](https://github.com/zhi35/iptv)：README 明确致谢并依赖 `fanmingming/live`，仓库历史显示只有一个提交；作为镜像没有足够独立来源价值，直接使用上游更透明。
- [fanmingming/live](https://github.com/fanmingming/live)：仓库截至 2026-07 仍有 Actions 更新，但[IPv6 播放列表自己的提交历史](https://github.com/fanmingming/live/commits/main/tv/m3u/ipv6.m3u)最后更新于 2025-05-09；近期活动主要是 EPG，不能据此认定直播线路近期维护。本项目已有其他上游覆盖其常见线路，可继续只使用台标/EPG 元数据。
- [HerbertHe/iptv-sources](https://github.com/HerbertHe/iptv-sources)：主要再次聚合 `iptv-org`、YueChan、fanmingming、joevess 等，且验流功能默认关闭；在现有池基础上重复率高。可用它发现上游，但不要把生成清单整体再次并入。
- [joevess/IPTV](https://github.com/joevess/IPTV)：README 最近列出的人工更新记录停在 2024-01，2026-08-02 打开的四个 Raw M3U 均只剩 `#EXTM3U` 头，当前没有可用候选。
- [cymz6/AutoIPTV-Hotel](https://github.com/cymz6/AutoIPTV-Hotel)：虽然声明每天更新，但 README 明确写明“所有内容未经人工审核，不排除某些内容可能会引起不适”，且仓库未显示许可证；不符合本项目对成人/异常内容和授权风险的准入要求。
- [frankwuzp/iptv-cn](https://github.com/frankwuzp/iptv-cn)：Actions 高频更新的是 EPG，直播清单的 changelog 与可用性说明停留在 2021 年，且部分文件明确来自更旧的 BurningC4 数据；不属于近期维护的直播线路。
- [stackia/hainan-telecom-iptv-updater](https://github.com/stackia/hainan-telecom-iptv-updater) 及其[海南电信 M3U gist](https://gist.github.com/stackia/9dba21f67df6cd3226d4776960ee289b)：2026 年仍有维护，但输出为海南电信专网 RTP 组播/FCC 地址，需要当地 IPTV VLAN 与 `rtp2httpd`，不适合当前公网 HLS 聚合订阅。
- [qwerttvv/Beijing-IPTV](https://github.com/qwerttvv/Beijing-IPTV)：维护的是北京联通/移动专网单播、组播列表，公网 Actions 无法验活；README 还明确包含“解锁”收费频道。即使仓库采用 CC0，也不适合当前面向全国公网 HLS 的订阅和授权边界。
- [BurningC4/Chinese-IPTV](https://github.com/BurningC4/Chinese-IPTV)：仓库当前只有 `TV-IPV4.m3u` 播放列表；README 明确记录“2025 年 9 月 3 日 IPv4 又不好使了，请切到 IPv6”，但仓库并没有对应 IPv6 播放列表。其高频活动主要是每小时更新 EPG，不能证明直播线路仍健康；页面也未显示明确 LICENSE，因此本轮不接入。
- [YanG-1989/m3u](https://github.com/YanG-1989/m3u)：README 自述“个人爱好，收集整合！佛系更新”，可见更新日志最近停在 2025-08-09，未发现持续自动验流或测速；列表混有香港频道、咪咕及其他直播平台/时效性地址，且页面未显示明确 LICENSE。独立性、时效性和内容边界均不足，本轮不接入。
- `drangjchen/IPTV` 等静态或“佛系更新”个人清单：缺少近期逐条自动验活，且大量内容已被其他聚合源重复收录，不满足本轮“近期仍维护、增加独立线路”的筛选标准。

## 接入约束

新增来源后仍应执行以下硬规则：

1. 只把上游当候选，不直接拼接发布；为每条 URL 保留 `source_repo`、抓取时间、IP 栈和探测节点运营商。
2. 只接受实际直播：HLS 必须没有 `#EXT-X-ENDLIST`，连续获取两个更新后的媒体清单/分片；拒绝固定短循环、电影剧集、直播平台轮播和 HTML 页面。
3. 国内归属必须由规范化频道名/频道字典确认；上游分组只能作为弱信号。显式排除港澳台、CGTN/CCTV 国际版本、海外、成人、购物和测试频道。
4. IPv4、IPv6 和运营商专网分开统计。公网构建失败不能把北京/海南等区域专网源判成“全局永久失效”，但区域源也不能混入全国默认订阅。
5. 同一 Host 大量频道通过不能替代逐频道内容校验；防止一个中转 Host 返回统一占位画面、广告或错误频道。
6. GitHub 仓库许可证只覆盖仓库作者的代码/编排。公开再分发第三方流地址、代理、转码或推流之前仍需确认源站条款和频道权利。
