# 项目审查：问题整理

**日期：** 2026-10-20
**范围：** `feat/board-game-agent` 分支（提交 `3254c1c`）
**状态：** 仅整理问题，尚未修复

代码约 1,300 行，31 个测试全部通过，整体结构与设计文档一致。问题按优先级分为两部分：第一部分是规则理解问题（决定建议是否正确），第二部分是工程与稳定性问题。

---

## 第一部分：agent 无法理解规则

**结论：** 模型从来没有拿到完整、可用的规则信息。原因有两层，另有若干放大因素。

### 证据

最近一次桌测（`sessions_table/20261012-150110/rounds/01.md`）第 1 轮，四个玩家中有三个犯了明显的规则错误：

- **B**：在 Birmingham 建 Pottery。印象中 Birmingham 没有陶器格，但无法用规则文本核对，因为文本中根本没有这类信息。
- **C**：一次 Build "使用手牌 Location:Uttoxeter + Industry:Pottery"，用了两张牌。
- **D**：一次 Build "使用手牌 Industry:Iron Works + Location:Kidderminster"，同样用了两张牌。

规则书写明：一次 Build 只弃一张合适的牌；且运河期第 1 轮每人只有 1 个行动。

### 根因一：桌测提示词里没有规则

`scripts/table_match.py` 中的 `build_act_prompt` 和 `agent_act` 的系统提示词只包含手牌、资金、市场和历史行动，既没有规则卡片，也没有规则原文。`init` 阶段提炼了规则，每个座位的 Session 也写入了 `card.json`，但 `step` 阶段从未读取。桌测中的每一步行动完全来自模型自身对 Brass 的记忆。

### 根因二：规则文本缺少版图数据

`fixtures/birmingham/rules.full.md` 是从 PDF 抽取的 42KB 文本。部分地名出现次数：

| 地名 | 出现次数 |
|---|---|
| Uttoxeter | 0 |
| Burton | 0 |
| Coalbrookdale | 0 |
| Kidderminster | 1 |
| Birmingham | 5 |

Brass 的合法性判断很大程度上依赖只画在版图和玩家板上的信息：

- **版图**：每个城市有哪些产业格、城市之间的运河/铁路连线、哪些城市连到哪个商人。
- **玩家板板块数据**：每一级板块的花费、所需煤铁、分数和收入增量。

这些信息在 PDF 转文本时全部丢失。即使把规则原文完整发给模型，它也无法判断"Birmingham 建陶器"是否合法。这也解释了为什么流程只追问 `hand`、`funds`、`phase`、`active_seat`：版图状态完全没有建模。

### 放大因素

1. **正式 `advise` 流程只拿到摘要。** `Strategist`、`LegalityChecker`、`Critic` 只看规则卡片（模型把 42KB 原文压缩成的约 7KB 摘要）。"一个行动只弃一张牌""运河期第 1 轮只有 1 个行动"等硬约束混在其他内容中不够突出。只有 `ask` 会发送完整原文。
2. **合法性检查只靠模型。** `LegalityChecker` 使用同一份摘要，模型不了解版图就发现不了错误，只会重复确认。代码中没有任何硬性校验，连"一个行动用了几张牌"都不检查。
3. **规则卡片缺少本局特定规则。** 例如四人局 Industry 卡只能在自己网络内建造，二/三人局放宽此限制；卡片中只有通用 Build 说明。
4. **PDF 抽取排版混乱。** 文本被切成碎片行，表格和图标全部丢失，导致规则卡片质量不高。
5. **无法衡量规则理解程度。** 没有测试检查 agent 是否懂规则（如"Birmingham 能建陶器吗？""一次 Build 用几张牌？"），修复后也无法证明效果。

### 修复方向（已选定方案 A，待实施）

1. 把规则卡片和相关原文章节接入桌测与 `advise` 的提示词。
2. 补充 Birmingham 版图与玩家板数据文件（作为游戏数据，不写死在代码中），并据此做确定性合法性检查。
3. 同步建立规则理解小测验，用于验证修复效果。

---

## 第二部分：工程与稳定性问题

### 确定的 bug

1. **每次建议都写进 `turns/1/`，旧记录被覆盖。** `Orchestrator._turn` 存在实例上，而 CLI 每条命令都新建实例，计数永远从 0 开始。应根据 `turns/` 已有目录数或 `meta.json` 计数。
2. **上帝视角信息进入策略提示词。** `GameState.out_of_view_notes` 随 `state.model_dump_json()` 一起传给 `Strategist`、`LegalityChecker`、`Critic`，违反设计文档的玩家视角约束。
3. **`undo` 只撤销一半。** 一次 `say` 可能产生多条事件，`undo` 只删最后一条；`assumptions.md` 和对话记录也不回滚。应按 `say` 批次整体撤销。
4. **可能卡在追问循环。** `missing_critical` 按固定键名 `funds`、`hand` 检查 `state.me`，但解析提示词未规定键名；模型写成 `money` 或 `资金` 时会无限追问。
5. **部分 agent 缺少容错。** `Strategist`、`LegalityChecker` 直接 `model_validate`，模型少返回一个字段即整次建议失败。
6. **`table_match.py` 潜在 `NameError`。** 第 184–191 行 try 块失败时 `store`、`sid` 未赋值，第 228 行使用时报错并被空 `except` 吞掉；第 187 行的 `orch` 未被使用。

### 设计文档中尚未实现

- 合法性结果只"告知"`Critic`，代码层面不过滤非法行动；"所有候选都非法"的情况未处理。
- CLI 不捕获 `ValueError`，用户会看到 Python 报错堆栈；空输入、超长输入未拒绝。
- `--verbose` 基本无作用（文档要求打印中间文件路径和候选、合法性摘要）。
- 事件缺少 `timestamp` 字段。
- `reducer` 忽略事件类型（`correction` 与普通事件同样处理），且只做浅层 `dict.update`，无法表达"打出一张牌"这类删除操作。

### 可靠性与成本

- **改用 JSON 模式。** 目前用贪婪正则 `\{[\s\S]*\}` 从回复中提取 JSON；`deepseek-chat` 支持 `response_format={"type": "json_object"}`。
- **利用 DeepSeek 前缀缓存。** 规则卡片放在各 agent 指令之后，提示词开头各不相同，缓存基本命中不了；应把规则卡片挪到最前作为固定前缀。
- **`advise` 太慢。** 串行调用三次模型，其中两次使用 `deepseek-reasoner`；可考虑合并合法性检查与 `Critic`，或并行检查。
- **`ask` 每次发送完整原文。** 42KB 规则每问一次都要付费；可按章节切分后检索。
- **超长规则书丢失中间部分。** `RuleIngestor` 只保留前 45k 和后 10k 字符；可改为分段提炼再合并。
- **写文件非原子操作。** 崩溃可能损坏 `state/current.json`；可先写临时文件再 `os.replace`（state 可由 timeline 重算，风险较小）。
- **重试过于简单。** 只重试一次、固定等待 0.5 秒、无超时配置，只捕获 `APIError`。

### 架构与工程

- **桌测脚本绕开主流程。** `table_match.py` 注释称其 "more reliable than multi-JSON advise pipeline"，说明正式流程实战中不可靠；脚本中资金不扣、手牌不变、行动不校验，无法用来评估建议质量。应先修好主流程，再让脚本走 `Orchestrator`。
- **Birmingham 专用代码在核心包内。** `src/board_game_agent/birmingham/` 与"游戏不写死"的目标冲突，建议移到 `scripts/` 或扩展目录。
- **新克隆仓库无法运行脚本。** `rules.full.md` 被 `.gitignore` 忽略，但脚本默认读取它；README 应说明生成方法。
- **测试只验证格式。** 31 个测试全部使用模拟模型；建议建立固定局面评测集，用真实 API 定期运行。
- **缺少工程配置。** 无 `ruff`、`mypy`，无 CI。
- **仓库整理。** 功能分支未合并回 `master`；工作目录有 `sessions_smoke/`、`sessions_smoke2/`、`advise_out.txt` 等临时产物。

---

## 优先级

1. 规则没有送到模型（第一部分根因一）。
2. 规则缺少版图数据（第一部分根因二）。
3. 合法性检查拦不住错误（第一部分放大因素 1、2）。
4. 第二部分的确定 bug。
5. 其余可靠性、成本与工程问题。
