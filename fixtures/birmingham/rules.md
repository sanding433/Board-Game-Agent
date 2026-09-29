# Brass: Birmingham — 本地规则说明

官方规则 PDF 与全文提取（仅本地，不进 git）：

- `fixtures/birmingham/Brass-Birmingham-Rulebook.pdf`（Roxley 官方）
- `fixtures/birmingham/rules.full.md`（PDF 文本提取，供 CLI ingest）

加载给 agent：

```powershell
py -3.12 -m board_game_agent rules fixtures\birmingham\rules.full.md
```

来源：http://files.roxley.com/Brass-Birmingham-Rulebook-2018.11.20-highlights.pdf  
版权归 Roxley Games；请勿把 PDF/全文提交进公开仓库。
