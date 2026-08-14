# Wire codec audit

CARE 的网络层只传输真实固定宽度 `bytes`，不直接传 Python 对象。
`UnreliableNetwork` 强制 `len(payload) == byte_size`，因此 attempted traffic
直接来自实际编码长度；被丢弃的数据包仍计费。

## 已验证不变量

- Cell Delta、Digest Query、Patch、ACK、Replica Digest 的长度分别为
  13 B、`16+6N` B、`4+13M` B、8 B、16 B；
- Scuttlebutt digest 为 `4+5R` B，Merkle probe/match 为 20/4 B，16-ary
  child response 为 260 B，21-cell IBLT sketch 为 491 B；
- 解码器拒绝错误长度、未知 wire version、非零保留位、越界字段和损坏的
  Delta CRC；
- 解码后的重复/转发 update 继续使用确定性的 version stamp 合并规则；
- 字段范围覆盖冻结实验的 64×64 地图、32 agents 和 64 steps；
- codec、transport、runner、周期同步和三个 published reconciliation
  baseline 均由自动测试覆盖；
- 69,800 次完整 protocol execution 中所有策略使用同一 codec 和计费路径；
- No Communication 的 600 个 episode 全部严格为 0 attempted bytes；
- Continuous Full Sync (`K=1`) 仍经过相同的 13-B cell delta、丢包链路、
  data cap 与 attempted-byte 计费，不使用理想无损旁路；
- Path-Aware、Single-Cell 与 CARE 共享 8-cell/64-B 最大 query，实际长度均由
  同一 encoder 生成并计费。

运行审计测试：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

完整字段布局和错误处理约定见 [`WIRE_FORMAT.md`](WIRE_FORMAT.md)。
