# CARE 代码架构与协作关系

本仓库只保留论文中使用的 CARE 显式地图副本实验链路。它不包含
CMVR/Oracle、EPOM 训练、学习型通信策略或外部 MARL 方法的复现。

## 端到端数据流

```mermaid
flowchart LR
  C[冻结 YAML 配置] --> R[scripts/run_psr_suite.py]
  R --> I[独立地图与匹配丢包轨迹]
  I --> E[cmvr.env.PSRClosedLoopRunner]
  E --> M[本地 BeliefMap + 稀疏版本化 update]
  E --> P[A* / 增量 D* Lite 路径规划]
  E --> N[UnreliableNetwork + 精确字节预算]
  E --> O[results.csv / traces.csv / instances]
  O --> A[分析脚本：均值、标准差、配对 bootstrap CI]
  A --> T[paper/tables 与 paper/figures]
  T --> X[paper/care_icassp_draft.tex]
```

每张地图有一个 `layout_seed` 和一个匹配的 `network_seed`。同一 map
下的所有策略共享地图、起终点和逐包丢失抽样键；因此策略差值可按 map
配对，而不是把独立的 episode 均值误当成配对证据。

## 核心包

| 路径 | 责任 | 与其他模块的协作 |
| --- | --- | --- |
| `cmvr/mapping/` | `BeliefMap`、cell stamp、局部观测编码、增量更新 | 环境将观测写入本地副本；网络交付的版本化 update 也在这里合并。 |
| `cmvr/planning/` | 统一 Planner 接口、确定性 A*、增量 D* Lite | runner 为每个 receiver 分别维护乐观/悲观规划器；CARE 只消费路径，不依赖具体搜索实现。 |
| `cmvr/communication/unreliable.py` | 有向、固定 seed 的丢包/延迟信道与 event log | 所有 delta、digest、ACK 和 repair 都经过同一对象；输出按 data/control/repair 分项计费。 |
| `cmvr/communication/replica_protocol.py` | policy、digest、scenario/deadline certificate 和 patch payload | 枚举有界稀疏场景并精确求解最小 hitting set；同时计算 route deadline；不访问真值地图或 peer 内存。 |
| `cmvr/communication/external_reconciliation.py` | Scuttlebutt 版本进度、Merkle 树、IBLT subtract-and-peel | 只读取显式 `BeliefMap`/版本 update；不访问 planner、真值地图或其他机器人的内存。 |
| `cmvr/communication/wire.py` | 固定宽度二进制 codec、CRC、字段边界和精确长度 | runner 在发送前编码、到达后解码；network 只接受 `bytes` 且强制 `len(payload) == byte_size`。 |
| `cmvr/env/instance.py`、`structured_instances.py` | 随机与决策关键拓扑实例 | 为所有配对策略生成同一个可指纹化实例；`layout_fingerprint` 只编码物理布局，不把 seed 标签伪装成地图差异。 |
| `cmvr/env/psr_runner.py` | 唯一的 closed-loop 执行器 | 编排观测、A*、通信、交付、修复与 POGEMA 动作，并生成 episode 级与 step 级指标。 |
| `cmvr/utils/` | 配置和随机种子 | 保证跨进程、跨重跑的一致性。 |

## 方法在同一 runner 中的差别

所有策略在每个 planner 条件内共享地图表示、每 sender 每步字节上限、链路丢失/延迟和
instance/loss trace。差别只在“何时修复”与“修复哪里”。

| 策略 | 何时修复 | 修复范围 |
| --- | --- | --- |
| One-shot | 从不 | 无；普通 delta 只尝试一次 |
| Retry-All / Path-Weighted | 每次需要重传时 | 缺失 delta |
| Periodic Full (K=4) | 每四步 | 已知全副本的公平轮转 chunk |
| Mismatch Full | replica digest 不一致时 | 全副本 chunk |
| PSR-UT | 本地乐观/悲观下一动作不同且在 corridor 内 | 接收端当前路径 corridor |
| CARE-Lite | 两条路径存在歧义且 query--patch 可在首次进入未知 cell 前返回 | 分叉到重合之间的一跳 action-graph 未知 influence set |
| CARE | 存在仍可及时修复的动作冲突场景对 | 精确最小 scenario hitting set；正延迟时并入 route-commitment certificate |
| Scuttlebutt-Depth | 周期性交换 per-origin 最大版本 | backlog 最深的 origin 优先，同源 update 按旧到新发送 |
| Dynamo-style Merkle AE | 会话内重试 16-ary 根/分支 hash，逐层恢复未匹配分支 | 深度优先定位不同 leaf，再发送该 cell；match ACK 使丢包后可继续 |
| Partitioned IBLT | 对同一 peer 连续轮转 16 个空间分片并交换固定大小 sketch | subtract-and-peel 恢复该分片集合差，再发送 local-only records |

Periodic Full 在非同步步发送普通 one-shot delta；同步步用同一 data cap
优先发送完整已知副本的一个 chunk。chunk 同时轮转 cell 和 receiver，避免
小预算下总是只发送给低编号机器人或只发送首批 cell。

## 编码、解码与计费

应用层实际发送固定宽度字节串，而不是直接在 network 中传递 Python
对象。Cell Delta 为 13 B，Digest Query 为 `16+6N` B，Patch 为
`4+13M` B，ACK 为 8 B，Replica Digest 为 16 B。发送预算使用编码后的
`len(payload)`，丢失包同样计入 attempted traffic。接收端先验证 wire
version、长度、保留位、字段边界与 Delta CRC，再重建 update 并按
`(version, observed_at, source_id, state)` 合并。完整字段与位布局见
[`docs/WIRE_FORMAT.md`](WIRE_FORMAT.md)。

## 脚本与结果契约

| 脚本 | 输入 | 输出 |
| --- | --- | --- |
| `run_psr_suite.py` | 一个 YAML 或等价 config | `instances/`、`results.csv`、`traces.csv`、`summary.json` |
| `run_care_extension_matrix.py` | 5×5 下的 density、topology、scale、q/cap/cadence 设计 | 12,000-episode manifest 与各 study 输出 |
| `analyze_care_observation_radius.py` | 3×3/5×5/7×7 的 6,000-episode 匹配矩阵 | FOV 汇总、配对差异、交互效应、因果时间和 cap 命中率 |
| `analyze_care_extension_matrix.py` | CARE extension manifest 与 5×5 主矩阵 | 均值/SD/CI、扩展配对比较、full-method ablation |
| `audit_care_cross_study_reproducibility.py` | 主/FOV/delay/density 独立重跑 | 除 CPU timing 外逐字段完全一致性审计 |
| `make_care_deadline_artifacts.py` | CARE analysis | 跨规划器主表和 delay figure |
| `analyze_care_certificate.py` | 双证书 3,200-episode gate | 配对 non-inferiority、traffic 和 CPU promotion gate |
| `analyze_care_loss_baselines.py` | 9,600-episode loss/baseline matrix | map-cluster CI、paired effect size 和 Pareto frontier |
| `make_care_loss_baseline_artifacts.py` | final audited analysis | 最终 baseline 表和 loss/traffic figure |
| `make_care_observation_radius_artifacts.py` | FOV analysis | 5×5 主表、3×3/7×7 扩展表与 FOV 图 |
| `make_care_extension_artifacts.py` | extension analysis | paired ablation、density/topology/scale/negative-control 表图 |
| `analyze_external_reconciliation.py` | 21,600-episode 三视野 published-baseline matrix | 完整性审计、均值/SD/CI、CARE 与 external 的配对效应、IBLT 解码率 |
| `make_external_reconciliation_artifacts.py` | external-baseline analysis | 投稿主表、配对表和协议诊断表 |

所有 runner 拒绝覆盖非空输出目录。这是为了防止新运行静默混入已冻结的
100-map 证据。完整命令见 `docs/REPRODUCIBILITY.md`。

## 测试边界

`tests/` 覆盖 A*、D* Lite 增量更新及 A* 最短路一致性、实例确定性、物理
layout 指纹与 100-map 唯一性、地图 stamp 合并、丢包链路、CARE runner、
周期反熵的预算/轮转、Scuttlebutt/Merkle/IBLT primitive 与 runner 集成、
因果时间/cap 指标，以及并行与串行结果一致性。运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```
