"""
Stepwise Brass: Birmingham 4-seat table match — one ROUND per step.

Usage:
  py scripts/table_match.py init --seed 42
  py scripts/table_match.py step                 # run next ROUND (A→B→C→D), write one file, exit
  py scripts/table_match.py step --run <id>

Each round writes: rounds/01.md with four blocks:
  === A ===
  行动。
  理由

  === B ===
  ...
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from board_game_agent.birmingham.setup import (
    STARTING_FUNDS,
    DealtSetup,
    MerchantPlacement,
    ResourceMarkets,
    MarketSpace,
    deal_opening_4p,
    describe_merchants,
)
from board_game_agent.config import Settings
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import RuleCard
from board_game_agent.orchestrator import Orchestrator
from board_game_agent.session.store import SessionStore

SEAT_NAMES = ["A", "B", "C", "D"]


def parse_action_reason(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    action_m = re.search(r"行动\s*[:：]\s*(.+)", raw)
    reason_m = re.search(r"理由\s*[:：]\s*(.+)", raw, re.S)
    if action_m:
        action = action_m.group(1).strip().splitlines()[0].strip().rstrip("。.;；")
        reason = "（未给出理由）"
        if reason_m:
            reason = reason_m.group(1).strip()
            reason = re.split(r"\n\s*(?:次选|风险|注意|候选)", reason)[0].strip()
            reason = " ".join(reason.split()) or reason
        return action, reason
    parts = re.split(r"(?<=[。.!！？])\s*", raw, maxsplit=1)
    action = (parts[0] if parts else raw).strip().rstrip("。.;；")
    reason = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "（未给出理由）"
    return action or "（未能解析行动）", " ".join(reason.split())


def format_agent_block(agent: str, action: str, reason: str) -> str:
    return f"=== {agent} ===\n{action.rstrip('。.;；')}。\n{reason}\n"


def dealt_to_dict(dealt: DealtSetup) -> dict:
    return {
        "hands": dealt.hands,
        "opening_discards": dealt.opening_discards,
        "draw_deck": dealt.draw_deck,
        "resource_markets": {
            "coal": [{"price": s.price, "has_cube": s.has_cube} for s in dealt.resource_markets.coal],
            "iron": [{"price": s.price, "has_cube": s.has_cube} for s in dealt.resource_markets.iron],
        },
        "merchants": [
            {
                "location": m.location,
                "tile": m.tile,
                "beer_bonus": m.beer_bonus,
                "has_beer": m.has_beer,
            }
            for m in dealt.merchants
        ],
    }


def dealt_from_dict(data: dict) -> DealtSetup:
    coal = [MarketSpace(**x) for x in data["resource_markets"]["coal"]]
    iron = [MarketSpace(**x) for x in data["resource_markets"]["iron"]]
    merchants = [MerchantPlacement(**m) for m in data["merchants"]]
    return DealtSetup(
        hands=data["hands"],
        opening_discards=data["opening_discards"],
        draw_deck=data["draw_deck"],
        resource_markets=ResourceMarkets(coal=coal, iron=iron),
        merchants=merchants,
    )


def format_public_economy(dealt: DealtSetup) -> str:
    return dealt.resource_markets.describe() + "\n" + describe_merchants(dealt.merchants)


def latest_run(out_root: Path) -> Path | None:
    if not out_root.exists():
        return None
    runs = sorted([p for p in out_root.iterdir() if p.is_dir()], reverse=True)
    return runs[0] if runs else None


def resolve_run_dir(out_root: Path, run: str | None) -> Path:
    if run:
        p = Path(run)
        if p.exists():
            return p
        maybe = out_root / run
        if maybe.exists():
            return maybe
        raise SystemExit(f"run not found: {run}")
    latest = latest_run(out_root)
    if latest is None:
        raise SystemExit("没有可续跑的 run，请先 init")
    return latest


def load_state(run_dir: Path) -> dict:
    return json.loads((run_dir / "state.json").read_text(encoding="utf-8"))


def save_state(run_dir: Path, state: dict) -> None:
    (run_dir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_act_prompt(
    agent: str,
    round_no: int,
    hand: list[str],
    discard: str,
    dealt: DealtSetup,
    history: list[str],
) -> str:
    hist = "\n".join(history[-12:]) if history else "（尚无公开行动）"
    return (
        f"这是一场 Brass: Birmingham 四人桌测。你是玩家 {agent}，当前运河期。\n"
        f"现在是第 {round_no} 轮，轮到你行动（本轮内 A→B→C→D 各行动一次）。\n"
        f"资金 £{STARTING_FUNDS}（开局资金；本桌测暂不精确扣费）。\n"
        f"手牌：{', '.join(hand)}。\n"
        f"开局弃牌（面朝下那张）：{discard}。\n"
        f"公开经济信息：\n{format_public_economy(dealt)}\n"
        f"近期公开行动：\n{hist}\n"
        f"不要发明未给出的牌/地点/已建产业。\n"
        f"最终回答严格两行：\n行动：<一句话>\n理由：<一句话>\n"
    )


def agent_act(
    settings: Settings,
    run_dir: Path,
    state: dict,
    agent: str,
    seat_idx: int,
    round_no: int,
    dealt: DealtSetup,
    history: list[str],
) -> tuple[str, str, str]:
    """One direct DeepSeek call per seat (more reliable than multi-JSON advise pipeline)."""
    llm = LLMClient(settings)
    prompt = build_act_prompt(
        agent,
        round_no,
        dealt.hands[seat_idx],
        dealt.opening_discards[seat_idx],
        dealt,
        history,
    )
    # Keep a transcript breadcrumb in that seat's session without blocking on advise JSON.
    try:
        seat_dir = run_dir / "players" / f"seat_{agent}"
        store = SessionStore(seat_dir)
        orch = Orchestrator(settings, llm, store)
        sid = state["seat_sids"][agent]
        store.set_current(sid)
        store.append_transcript(sid, f"USER_ACT_PROMPT:\n{prompt}")
    except Exception as exc:  # noqa: BLE001
        print(f"[round] {agent} transcript skip: {exc}", flush=True)

    last_err: Exception | None = None
    formatted = ""
    for attempt in range(3):
        try:
            formatted = llm.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 Brass: Birmingham 玩家顾问。只根据给定信息决策。"
                            "必须选择一个可执行行动（Build/Network/Develop/Sell/Loan/Scout/Pass），"
                            "不要只说澄清或等待。严格输出两行：行动：... / 理由：..."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tier="fast",
            )
            if not (formatted or "").strip():
                raise ValueError("empty chat response")
            action, reason = parse_action_reason(formatted)
            if action.startswith("（未能") or "澄清" in action:
                raise ValueError(f"unusable action: {formatted[:120]}")
            last_err = None
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"[round] {agent} attempt {attempt + 1} failed: {exc}", flush=True)
            time.sleep(1.0)
    if last_err is not None:
        raise RuntimeError(f"player {agent} failed: {last_err}")

    action, reason = parse_action_reason(formatted)
    try:
        store.append_transcript(sid, f"ACTION:\n{format_agent_block(agent, action, reason)}")
    except Exception:
        pass
    return action, reason, format_agent_block(agent, action, reason)


def broadcast_observe(
    settings: Settings,
    run_dir: Path,
    state: dict,
    actor: str,
    action: str,
    reason: str,
    dealt: DealtSetup,
) -> None:
    public = (
        f"公开信息：玩家 {actor} 执行了行动：{action}。\n理由：{reason}\n"
        f"公开经济信息：\n{format_public_economy(dealt)}\n"
    )
    for other in SEAT_NAMES:
        if other == actor:
            continue
        try:
            seat_dir = run_dir / "players" / f"seat_{other}"
            store = SessionStore(seat_dir)
            sid = state["seat_sids"][other]
            store.append_transcript(sid, f"OBSERVE:\n{public}")
        except Exception as exc:  # noqa: BLE001
            print(f"[round] observe {other} skipped: {exc}", flush=True)


def cmd_init(args: argparse.Namespace) -> None:
    settings = Settings()
    if not settings.deepseek_api_key:
        raise SystemExit("缺少 DEEPSEEK_API_KEY（.env）")
    rules_path: Path = args.rules
    if not rules_path.exists():
        raise SystemExit(f"rules not found: {rules_path}")

    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_dir = args.out / run_id
    (run_dir / "rounds").mkdir(parents=True)
    (run_dir / "players").mkdir(parents=True)

    rng = random.Random(args.seed)
    dealt = deal_opening_4p(rng)

    print(f"[init] run={run_id} seed={args.seed} max_rounds={args.max_rounds}", flush=True)
    print("[init] ingesting rules once...", flush=True)
    ingest_store = SessionStore(run_dir / "rules_ingest")
    orch = Orchestrator(settings, LLMClient(settings), ingest_store)
    sid = orch.new_session(name="rules-ingest")
    orch.load_rules(sid, rules_path)
    card = ingest_store.read_rule_card(sid)
    assert card is not None
    card_dict = card.model_dump()
    rules_text = rules_path.read_text(encoding="utf-8")
    (run_dir / "rule_card.json").write_text(
        json.dumps(card_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "rules.raw.md").write_text(rules_text, encoding="utf-8")

    seat_sids: dict[str, str] = {}
    for agent in SEAT_NAMES:
        seat_dir = run_dir / "players" / f"seat_{agent}"
        store = SessionStore(seat_dir)
        seat_orch = Orchestrator(settings, LLMClient(settings), store)
        seat_sid = seat_orch.new_session(name=f"table-{agent}")
        seat_orch.load_rules_prepared(seat_sid, rules_text, RuleCard.model_validate(card_dict))
        seat_sids[agent] = seat_sid
        print(f"[init] player {agent} sid={seat_sid}", flush=True)

    setup_lines = [
        f"# Setup seed={args.seed}",
        f"funds=£{STARTING_FUNDS}",
        "",
        format_public_economy(dealt),
        "",
    ]
    for i, agent in enumerate(SEAT_NAMES):
        setup_lines.append(f"## {agent}")
        setup_lines.append("hand: " + ", ".join(dealt.hands[i]))
        setup_lines.append(f"opening_discard: {dealt.opening_discards[i]}")
        setup_lines.append("")
    (run_dir / "00_setup.md").write_text("\n".join(setup_lines), encoding="utf-8")

    state = {
        "run_id": run_id,
        "seed": args.seed,
        "next_round": 1,
        "max_rounds": args.max_rounds,
        "seat_sids": seat_sids,
        "history": [],
        "dealt": dealt_to_dict(dealt),
    }
    save_state(run_dir, state)
    print(f"[init] wrote {run_dir / '00_setup.md'}", flush=True)
    print(f"[init] next: py scripts/table_match.py step --run {run_id}", flush=True)


def cmd_step(args: argparse.Namespace) -> None:
    """Run one full round: A → B → C → D, write one file, exit."""
    settings = Settings()
    if not settings.deepseek_api_key:
        raise SystemExit("缺少 DEEPSEEK_API_KEY（.env）")

    run_dir = resolve_run_dir(args.out, args.run)
    state = load_state(run_dir)
    round_no = int(state["next_round"])
    max_rounds = int(state.get("max_rounds", 1))
    if round_no > max_rounds:
        print(f"[step] already finished ({max_rounds} rounds). run={run_dir.name}", flush=True)
        return

    dealt = dealt_from_dict(state["dealt"])
    history: list[str] = list(state.get("history") or [])

    print(f"[step] run={run_dir.name} round={round_no} (A→B→C→D)", flush=True)

    blocks: list[str] = [f"# 第 {round_no} 轮\n"]
    for seat_idx, agent in enumerate(SEAT_NAMES):
        print(f"[step] {agent} acting...", flush=True)
        action, reason, block = agent_act(
            settings, run_dir, state, agent, seat_idx, round_no, dealt, history
        )
        blocks.append(block)
        history.append(f"{agent}: {action}")
        print(block, flush=True)
        broadcast_observe(settings, run_dir, state, agent, action, reason, dealt)

    round_path = run_dir / "rounds" / f"{round_no:02d}.md"
    round_path.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    print(f"[step] wrote {round_path}", flush=True)

    state["history"] = history
    state["next_round"] = round_no + 1
    save_state(run_dir, state)

    if round_no >= max_rounds:
        print(f"[step] match finished ({max_rounds} rounds).", flush=True)
    else:
        print(
            f"[step] next round={round_no + 1}. "
            f"py scripts/table_match.py step --run {run_dir.name}",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Stepwise Brass table match (one ROUND per step)")
    parser.add_argument("--out", type=Path, default=ROOT / "sessions_table")
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT / "fixtures" / "birmingham" / "rules.full.md",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="deal + ingest + create players A-D")
    p_init.add_argument("--seed", type=int, default=42)
    p_init.add_argument("--max-rounds", type=int, default=1, help="how many A-D rounds to allow")
    p_init.set_defaults(func=cmd_init)

    p_step = sub.add_parser("step", help="run one round (A→B→C→D), write rounds/NN.md, exit")
    p_step.add_argument("--run", default=None, help="run id; default=latest")
    p_step.set_defaults(func=cmd_step)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
