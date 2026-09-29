# Board Game Agent

面向「一整局」桌游的多 Agent CLI 顾问：自然语言描述可见局面，站在**当前玩家视角**给出近似最优建议。MVP 使用 **DeepSeek API**（OpenAI 兼容）。

## Setup

需要 Python 3.11+。

```powershell
cd ".worktrees\feat-board-game-agent"   # 若在 worktree 中开发
py -3.12 -m pip install -e ".[dev]"
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

## CLI

```powershell
py -3.12 -m board_game_agent --help
py -3.12 -m board_game_agent new --name toy
py -3.12 -m board_game_agent rules fixtures\toy_game\rules.md
py -3.12 -m board_game_agent say "进入 play，轮到我"
# 缺关键信息会先追问；补全后：
py -3.12 -m board_game_agent advise
py -3.12 -m board_game_agent status
```

也可使用入口 `bga`（需把 Python Scripts 目录加入 PATH）。

## 桌测（Brass: Birmingham）

1. 准备自备规则 Markdown（不要依赖仓库内占位文件作为完整规则）。
2. 按 `fixtures/birmingham/scripts/opening_missing_hand.md` 走一遍。
3. 线下与朋友对局时，用 `say` 同步可见信息，结束看 `sessions/<id>/transcript.md`。

## 测试

```powershell
py -3.12 -m pytest -v
```

默认全部 mock，不访问网络。

## 说明

输出是玩家视角下的可执行建议，不是全局完美求解。缺 `hand` / `funds` / `phase` / `active_seat` 等关键槽位时会先追问再建议。
