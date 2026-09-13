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

## 一次性探针（保留作为排查过程存档）

`probe.py` / `probe2.py`（巨潮 API 参数、分页、招股书检索姿势）、`debug1.py`~`debug4.py`（三季报标题变体、北交所代码重复、分页上限、招股书 0 命中根因）、
`probe5.py`~`probe9.py`（年报正本不在 category、标题变体、残留漏档查证）、`diag_missing.py` / `diag2.py`（早期归因尝试，判据有误已被 `diag3.py` 取代）。

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
