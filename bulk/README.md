# bulk · 批量下载驱动层

在 `scripts/`（原工具的底座）之上，把「按单只股票查询」扩展成「全 A 股批量抓取」。
原工具只支持逐只股票调用；本目录是 2022 年至今全市场财报 + 招股书批量下载的实际执行层。

## 主流程

| 文件 | 用途 |
|---|---|
| `bulk_cninfo.py` | **主驱动器**。子命令 `run`（下载）/ `survey`（抽样规模测算）。支持并发、失败重试、断点续传（`_state/done.jsonl`）、落盘清单 `manifest.csv` |
| `run_full.ps1` | 全量启动器（独立进程，会话中断不杀任务）。把 Python 日志写进 `_state/run-*.log` |
| `status.ps1` | 打印进度：日志尾部、落盘文件数/体积、任务 ok/empty/fail、总进度 |
| `waitcheck.ps1` | 等待 N 秒后输出进度快照（`-View brief｜full`）。**注意 PowerShell 的 `1GB` 是 2³⁰（GiB），与 Python 的 `/1e9` 十进制 GB 不同** |

## 校验与维护

| 文件 | 用途 |
|---|---|
| `verify.py` | 完整性校验：任务状态、失败明细、空结果归因、缺失文件、分类型×年份覆盖率表、<10KB 疑似损坏、300 份随机 `%PDF-` 头抽检、与 manifest 对账 → 落 `_state/verify_report.md` |
| `diag3.py` | **空结果三分类归因**：`已退市/停牌` vs `当时尚未上市` vs `在市但仍漏档`。第三类才是真问题——这是发现系统性漏档的关键工具（见下） |
| `reconcile.py` | 对账「状态记录引用的体积」与「磁盘实际枚举体积」，排查差异 |
| `analyze.py` | 样本统计外推全市场文件数/体积 |
| `retry_empty.py` | 剔除 `status=empty` 记录使其重跑（修正筛选规则后回收漏档用） |
| `reset_type.py` | 剔除指定类型记录使其重跑 |

## 按披露日期归档（增量层）

| 文件 | 用途 |
|---|---|
| `fetch_by_date.py` | **按披露日期增量抓取**。把最新一批三季报 / IPO 招股书 / 业绩预告 / 业绩快报落到 `{root}/by_date/{YYYY-MM-DD}/财报|IPO|业绩预告|业绩快报/`，目录名即披露日期。子命令 `run`（下载）/ `list`（只列出）/ `mirror`（补镜像）/ `migrate`（旧目录搬迁） |
| `watch_season.ps1` | **报告季值守守护**。按固定间隔循环调用 `run`，每轮取「最近 N 天」滑动窗口，漏跑自愈（见下） |
| `backfill_yjyg.ps1` | **历史回填**「业绩预告 + 业绩快报」到 `by_date/`。按年循环（理由见脚本注释） |
| `check_manifest.py` | 快速核对 `manifest.csv`：行数、排序、按类型×年份分布、指向文件是否存在。搬镜像 / 搬迁目录后跑一次 |

数据流（`--streams`，逗号分隔，默认 `q3,ipo,yjyg,yjkb`）：

| 流 | 内容 | 落盘 |
|---|---|---|
| `q3` | 三季报正本 | `by_date/{日期}/财报/` + 镜像进 `reports/{年}/q3/` |
| `ipo` | 首发招股说明书 | `by_date/{日期}/IPO/` |
| `yjyg` | 业绩预告族（预告/预增/预盈/预减/预亏/预平，含修正稿） | `by_date/{日期}/业绩预告/` |
| `yjkb` | 业绩快报 | `by_date/{日期}/业绩快报/` |

`yjyg` 与 `yjkb` **共用同一次 category 检索**（业绩快报本来就在
`category_yjygjxz_szsh` 的结果里），所以启用 `yjkb` 不额外发任何请求。

与 `bulk_cninfo.py` 的分工：后者是**存量全量**（5,927 只股票 × 类型 × 年份，
落 `reports/{年}/{类型}/`）；前者是**增量按披露日期**（全市场 + `seDate` 区间检索，
落 `by_date/{披露日期}/`），用于跟踪「正在披露中」的报告季。

**两份落盘同时进行**：三季报除落到日期目录外，还会**硬链接**一份到既有结构
`reports/{年}/q3/` 并追加进 `manifest.csv`（排序口径与 `bulk_cninfo.write_manifest`
一致），使原数据集口径保持完整。硬链接在同一卷上零额外占用；跨卷自动退回复制。

**按「区间」检索，不是按天**（v2 起，性能差一个数量级）。巨潮 `seDate` 接受
`"起~止"` 区间，返回的每条公告自带 `announcementTime`，本地按它分桶就能一次
填出多天的日期目录。所以请求数**只取决于命中总数（÷30），与区间开多宽无关**：
逐日扫描则每天至少一次请求（哪怕当天什么都没披露），跨 5 年就是 1700+ 次，
纯属浪费。实测同一个 41 天窗口：逐日扫描约 40 秒 / 123 次请求 → 区间检索
**2 秒**，候选数完全一致（43 条）。

区间唯一的风险是「结果数 ÷ 30」超过 `--max-pages`（默认 250，即 7500 条）。
撞上限时 `_fill_range()` 会**自动二分区间递归**，直到单日为止，因此不会静默截断。
强制验证：把 `--max-pages` 压到 2（必然撞上限），该 41 天窗口仍返回同样的 43 条。

```bash
python fetch_by_date.py run  --root "C:\Users\iq112\Documents\cninfo" \
    --since 2026-09-01 --until 2026-10-10 --streams q3,ipo,yjyg --report-year 2026
python fetch_by_date.py list --root "C:\Users\iq112\Documents\cninfo" \
    --since 2025-10-31 --until 2025-10-31 --streams q3 --report-year 2025
python fetch_by_date.py mirror  --root "C:\Users\iq112\Documents\cninfo"   # 补镜像
python fetch_by_date.py migrate --root "C:\Users\iq112\Documents\cninfo"   # 旧布局搬迁
```

落盘索引：`{root}/_state/by_date.jsonl`（追加）+ `{root}/manifest_by_date.csv`（全量重写）。
日志：`{root}/_state/fetch_by_date-<时间戳>.log` 与 `{root}/_state/watch_season-<日期>.log`（均 UTF-8）。

### 报告季值守：什么节奏、为什么滑动窗口

```powershell
pwsh -File watch_season.ps1                    # 默认 8 小时一轮、回看 7 天、跑到 2026-11-05
pwsh -File watch_season.ps1 -IntervalHours 24  # 改成每天一轮
```

2025 年三季报季实测逐日正本数（用 `list` 实测，用于预判 2026 节奏）：

| 日期 | 10-11 | 10-13 | 10-14 | 10-15 | 10-16 | 10-17 | 10-18 | 10-20 | 10-21 | 10-22 | 10-23 | 10-24 | 10-25 | 10-27 | 10-29 | 10-30 | 10-31 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 家数 | 2 | 1 | 2 | 7 | 14 | 12 | 33 | 9 | 62 | 80 | 153 | 253 | 459 | 246 | 708 | 1160 | 1732 |

→ 首批约 10-11 出现，10-21 起放量，10-29~31 为高峰，整季约 5,400 份。

每轮用「最近 7 天」而不是「只抓当天」：三季报在披露季里是回溯补发的，某天漏跑
一轮，只抓当天就永久缺那一天；7 天窗口让漏跑自动自愈，而重复内容靠去重跳过，
代价只是多几次 HTTP 查询。

### 三季报「正本」识别（新增坑，勿退回关键词匹配）

`category_sjdbg_szsh` 是**季度报告大类**，不是三季报专属。实测 2026-10-09 单日
该 category 返回 128 条，几乎全是标题里同样含「第三季度」的干扰公告：
可转债转股情况公告、股票期权自主行权结果公告、业绩预告/快报、业绩说明会预告。
用「包含关键词」式匹配会把这些全部误当正本抓下来。

正规三季报标题的判别特征是**以「(第)三季度报告」结尾**，因此 `fetch_by_date.py`
改用锚定结尾的正则 `Q3_TITLE_RE` + 排除词双闸门。实测校验：2025-10-31 单日
过滤出 **1114 份**正本（category 原始 1132 条），「转股/行权/预告/说明会/公告/
摘要/更正/英文」命中数全为 **0**。

历史上按股票逐家跑（`bulk_cninfo.py`）用的 `reports.filter_report` 是按
「标题含 title_patterns + 标题最短」挑正本，逐家查询时噪声被公司维度天然隔离，
所以没暴露这个问题；**全市场检索必须换成锚定正则**。

### 业绩预告识别（找到了权威 category）

**`category_yjygjxz_szsh` = 业绩预告**（`yjyg` + `jxz` = 已预告及修正）。
这个码不是猜出来的，是从巨潮公告检索页的前端包里抠出来的：

```
http://www.cninfo.com.cn/new/js/app/disclosure/notice/history-notice.js?v=...
  → {"key": "category_yjygjxz_szsh", "value": "业绩预告"}
```

**那个 JS 里有完整、权威的 67 个 category 码**（年报/半年报/一季报/三季报/业绩预告/
权益分派/董事会/监事会/股东会/日常经营/公司治理/中介报告/首发/增发/股权激励/配股/
解禁/公司债/可转债/其他融资/股权变动/补充更正/澄清致歉/风险提示/特别处理和退市/
退市整理期，加上北交所 `_szdy` 系列与基金、债券系列）。**以后不要再靠猜拼法**，
直接 `grep 'category_[a-z0-9_]*' history-notice.js` 即可。（前端包已存一份在
`bulk/_tmp_cninfo/history-notice.js`。）

**坑（仍然重要）：无效 category 会被静默忽略。** `category_yjyg_szsh` /
`category_yjkb_szsh` / `category_yjyg` / `category_cg_yjyg_szsh` 等十余种「看起来对」
的拼法全部**不存在**，而巨潮不报错，直接退化成「全市场最新 30 条」，返回的是
「关于股东股份被司法强制卖出的公告」这类完全无关的内容。判别方法（值得复用）：
把带 category 的返回 `announcementId` 与**完全不传 category** 的基线做指纹比对，
一致即被忽略。

**实测该 category 的收益（`probe_yjyg_cat.py`）**：

| 窗口 | `category_yjygjxz_szsh` | `searchkey=业绩` 宽词 | 宽词正则命中 | category 漏掉的 |
|---|---|---|---|---|
| 2025-10 整月 | **129** | 1355 | 122 | **0** |
| 2026-10-01~11 | **20** | 85 | 19 | **0** |

→ category 不但真过滤（噪声≈0），而且**全覆盖**正则能抓到的东西；多出来的 7 条
全部是业绩快报 —— 即该 category 本身就含「业绩快报」。所以检索量比宽词降一个
数量级，且不必再靠 `searchkey` 兜底。`yjyg` 和 `yjkb` 两个流共用这一次检索，
再各自用正则分流。

**没有业绩快报的独立 category。** 完整 67 个码里没有「业绩快报」这一项，它归在
`category_yjygjxz_szsh` 里，只能靠 `YJKB_TITLE_RE = 业绩\s*快报` 从结果中分流。

用正则收紧而非放宽：`YJYG_TITLE_RE = 业绩\s*(预告|预增|预盈|预减|预亏|预平)`。
（早期走宽词时对 85 条实测：命中 20 条全部是真预告、未命中 65 条全部是业绩说明会 /
股权激励业绩考核指标 / 业绩补偿进展等噪声。现在 category 已把这些噪声挡在门外，
正则只负责在 category 结果里分流 预告 vs 快报。）

**这两个正则会漏掉东西吗？不会 —— 实测 0 漏口。** `probe_yjyg_gap.py` 把
category 取回的结果同时喂给两个正则，统计「两个都没命中」的条数：

| 窗口 | category 取回 | 预告正则 | 快报正则 | 两个都没命中 |
|---|---|---|---|---|
| 2025-04 一季报预告轮 | 373 | 287 | 99 | **0** |
| 2026-01 年报预告轮（最大一轮） | 3098 | 3029 | 70 | **0** |
| 2025-10 三季报预告轮 | 129 | 122 | 7 | **0** |

即 category 的结果被两个正则 100% 覆盖，不存在被静默丢弃的条目。
（`2026-01` 单月 3098 条就是全年最大的一轮 —— 年报预告。）

注意 `YJYG_EXTRA_EXCLUDE` **故意不继承** `reports.EXCLUDE_KEYWORDS`：那份清单含
「更正/补充/修改」，而「业绩预告更正公告」恰恰是有独立披露日期、且会改变预告数值
的必须留下的文件。

**同一家公司同一天可能有多份**（预告 + 修正稿），因此 `yjyg`/`yjkb` 不能用
`kind|code|date` 当唯一键（`MULTI_PER_DAY`），键会追加标题哈希；文件名直接用
公告标题（标题自带期间，如「2026年前三季度业绩预告」）。

业绩预告的季节节奏（`searchkey=业绩` 每日条数，含说明会噪声，真实预告数低于此）：
2025 年 10-10 起跳（47/35），10-28~10-31 为高峰（116/136/215/233），11 月初
还有第二波（11-04:68、11-05:74）；2026 年 10-08 起跳（12 → 10-09:39 → 10-10:19）。

## 一次性探针（保留作为排查过程存档）

`probe.py` / `probe2.py`（巨潮 API 参数、分页、招股书检索姿势）、`debug1.py`~`debug4.py`（三季报标题变体、北交所代码重复、分页上限、招股书 0 命中根因）、
`probe5.py`~`probe9.py`（年报正本不在 category、标题变体、残留漏档查证）、`diag_missing.py` / `diag2.py`（早期归因尝试，判据有误已被 `diag3.py` 取代）。
另有 2026-10 新增的日期检索探针：`probe_date.py`（全市场+日期区间可行性）、
`probe_date2.py`（用 2025-10 窗口对照验证 category 是否在全市场模式下生效）、
`probe_new.py`（盘点既有数据集清单的最新披露日期）、`probe_scale.py`（两种口径规模测算）、
`probe_q3verify.py` / `probe_q3verify2.py` / `probe_q3verify3.py`（三轮独立路径核查
「2026 三季报是否真的只有 1 份」）、`probe_yjyg.py` / `probe_yjyg2.py` / `probe_yjyg3.py`
（业绩预告的检索姿势）、`probe_yjyg_cat.py`（**验证 category_yjygjxz_szsh 真过滤且全覆盖**）、
`probe_yjyg_years.py`（按年估算业绩类公告规模，跑回填前用它算工作量）、
`probe_yjyg_gap.py`（**量化两个正则的漏口，实测 0**）。

参考存档：`refs/history-notice.js` —— 巨潮公告检索页的前端包，内含**全部 67 个权威
category 码**。以后新增数据流时先 grep 它，别再猜拼法。

## 踩过的坑（原工具的真实缺陷）

1. **`startDate`/`endDate` 被巨潮静默忽略** —— 真实参数是 `seDate="起~止"`。不修会拿到错误年份的数据
2. **`detect_column()` 不认北交所** —— 4/8/920 开头需返回 `bj`，否则被当成深交所
3. **`pageSize` 服务端上限为 30** —— 传更大值无效，必须靠 `pageNum` 翻页
4. **`searchkey` 与 `category` 同时为空时接口退化** —— 返回「最新 30 条」且 `hasMore=False`，导致招股书（无 category）永远检索不到
5. **年报正本可能不在 `category_ndbg_szsh` 里** —— 中国联通/东方证券/四川成渝等公司带 category 查只返回「摘要」，须去掉 category 改用 `searchkey` 兜底
6. **标题变体极多** —— 「年度报告」/「年报」（中国石油、锦江酒店，后者标题连年份都没有）、「第三季度报告」/「三季度报告」、「第一季度报告」/「一季度报告」/「季度报告」/「季报」/「报」（创力集团、顾家家居）。单一关键词会整批漏档，故 `reports.py` 改用 `title_patterns` 多模式匹配

第 5、6 项是首轮跑完后通过 `diag3.py` 归因才发现的：先区分「退市空壳」与「在市公司」，再逐家核对原始公告，最终回收 282 份漏档。

## 用法

```bash
# 全量下载（断点续传，重跑同一条命令即可）
python bulk_cninfo.py run --root "C:\Users\iq112\Documents\cninfo" --workers 10

# 小样本试跑 / 规模测算
python bulk_cninfo.py run --root D:\test --sample 20
python bulk_cninfo.py survey --root D:\test --sample 60

# 校验 / 归因
python verify.py "C:\Users\iq112\Documents\cninfo"
python diag3.py annual 2025 8
```
