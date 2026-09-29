# Opening beat — missing hand (human checklist)

1. `bga new --name birmingham-table`
2. `bga rules fixtures/birmingham/rules.md`（或你的完整规则 Markdown）
3. `bga say "运河期，轮到我了"`
4. **期望**：先追问手牌/资金等 critical_slots，不直接瞎给建议
5. `bga say "手牌：棉纺、煤矿；资金 £30；我是座位 A"`
6. `bga advise`
7. **期望**：给出可执行行动建议与简短理由
8. 对局结束后查看 `sessions/<id>/transcript.md` 与 `timeline.jsonl`
