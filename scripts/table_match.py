"""
Four-seat auto table match for Brass: Birmingham smoke demo.

- 1 referee process + 4 independent player processes
- Starting funds fixed at £17
- Hands and coal/iron market randomized
- Each seat's advise text is treated as its action and broadcast to the other three
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from board_game_agent.config import Settings
from board_game_agent.llm.client import LLMClient
from board_game_agent.models.schemas import RuleCard
from board_game_agent.orchestrator import Orchestrator
from board_game_agent.session.store import SessionStore

STARTING_FUNDS = 17
HAND_SIZE = 8
SEAT_NAMES = ["A", "B", "C", "D"]

# Simplified industry/location deck for dealing (demo; not a full official card list)
DEMO_DECK = [
    "棉纺厂",
    "煤矿",
    "铁厂",
    "啤酒厂",
    "陶器",
    "伯明翰",
    "考文垂",
    "伍尔弗汉普顿",
    "斯塔福德",
    "什鲁斯伯里",
    "伍斯特",
    "牛津",
    "格洛斯特",
    "雷丁",
    "楠特威奇",
    "斯托克",
    "德比",
    "诺丁汉",
    "瓦克菲尔德",
    "谢菲尔德",
    "贝洛普",
    "基德明斯特",
    "雷迪奇",
    "坦沃思",
    "伯顿",
    "勒顿",
    "韦姆",
    "坎诺克",
    "达德利",
    "沃尔索尔",
    "煤矿",
    "铁厂",
    "啤酒厂",
    "棉纺厂",
    "陶器",
    "啤酒厂",
    "煤矿",
    "铁厂",
    "棉纺厂",
    "陶器",
]


def deal_hands(rng: random.Random) -> list[list[str]]:
    deck = DEMO_DECK[:]
    rng.shuffle(deck)
    hands: list[list[str]] = []
    for i in range(4):
        start = i * HAND_SIZE
        hands.append(deck[start : start + HAND_SIZE])
    return hands


def random_market(rng: random.Random) -> dict:
    # Demo-only public market snapshot (not a full rules engine)
    return {
        "coal_spaces_filled": rng.randint(0, 8),
        "iron_spaces_filled": rng.randint(0, 8),
        "coal_note": "煤市场可见空位/已填档位如上（演示随机）",
        "iron_note": "铁市场可见空位/已填档位如上（演示随机）",
    }


def format_market(market: dict) -> str:
    return (
        f"煤市场已填档约 {market['coal_spaces_filled']}；"
        f"铁市场已填档约 {market['iron_spaces_filled']}。"
        f"{market['coal_note']}；{market['iron_note']}"
    )


def player_process(
    seat: int,
    in_q: mp.Queue,
    out_q: mp.Queue,
    sessions_root: str,
    rules_text: str,
    card_dict: dict,
    llm_cfg: dict,
) -> None:
    settings = Settings(
        sessions_dir=Path(sessions_root) / f"seat_{SEAT_NAMES[seat]}",
        deepseek_api_key=llm_cfg["deepseek_api_key"],
        deepseek_base_url=llm_cfg["deepseek_base_url"],
        model_fast=llm_cfg["model_fast"],
        model_reasoning=llm_cfg["model_reasoning"],
        reply_language="zh",
        auto_advise_after_say=False,
    )
    orch = Orchestrator(settings, LLMClient(settings), SessionStore(settings.sessions_dir))
    sid = orch.new_session(name=f"table-seat-{SEAT_NAMES[seat]}")
    orch.load_rules_prepared(sid, rules_text, RuleCard.model_validate(card_dict))
    out_q.put({"seat": seat, "type": "ready", "sid": sid})

    while True:
        msg = in_q.get()
        if msg.get("type") == "stop":
            break
        text = msg.get("text", "")
        try:
            if msg.get("type") == "act":
                ack = orch.say(sid, text)
                # If still clarifying, force advise may re-ask; include full state in act prompts.
                advice = orch.advise(sid)
                out_q.put(
                    {
                        "seat": seat,
                        "type": "action",
                        "ack": ack,
                        "action": advice,
                    }
                )
            elif msg.get("type") == "observe":
                ack = orch.say(sid, text)
                out_q.put({"seat": seat, "type": "observed", "ack": ack})
            else:
                out_q.put({"seat": seat, "type": "error", "error": f"unknown msg {msg}"})
        except Exception as exc:  # noqa: BLE001 - surface to referee for demo
            out_q.put({"seat": seat, "type": "error", "error": str(exc)})


def wait_ready(out_q: mp.Queue, n: int, timeout: float = 600.0) -> None:
    ready = 0
    deadline = time.time() + timeout
    while ready < n:
        if time.time() > deadline:
            raise TimeoutError("players failed to become ready")
        msg = out_q.get(timeout=max(1.0, deadline - time.time()))
        if msg.get("type") == "ready":
            ready += 1
            print(f"[table] seat {SEAT_NAMES[msg['seat']]} ready sid={msg.get('sid')}", flush=True)
        elif msg.get("type") == "error":
            raise RuntimeError(f"seat init error: {msg}")


def drain_matching(
    out_q: mp.Queue,
    want_seats: set[int],
    expect: str,
    timeout: float = 600.0,
) -> dict[int, dict]:
    """Collect one message of `expect` from each seat in want_seats (order-independent)."""
    deadline = time.time() + timeout
    got: dict[int, dict] = {}
    pending = set(want_seats)
    while pending:
        if time.time() > deadline:
            raise TimeoutError(f"timeout waiting {expect} from seats {sorted(pending)}")
        try:
            msg = out_q.get(timeout=max(1.0, deadline - time.time()))
        except Exception as exc:  # queue.Empty
            raise TimeoutError(f"timeout waiting {expect} from seats {sorted(pending)}") from exc
        seat = msg.get("seat")
        if msg.get("type") == "error" and seat in pending:
            raise RuntimeError(f"seat {SEAT_NAMES[seat]} error: {msg.get('error')}")
        if msg.get("type") == expect and seat in pending:
            got[int(seat)] = msg
            pending.remove(int(seat))
        else:
            print(
                f"[table] buffer-ignore type={msg.get('type')} seat={msg.get('seat')} "
                f"while waiting {expect} from {sorted(pending)}",
                flush=True,
            )
    return got


def build_private_prompt(
    seat: int,
    hand: list[str],
    market: dict,
    beat: int,
    history: list[str],
) -> str:
    hist = "\n".join(history[-8:]) if history else "（尚无公开行动）"
    return (
        f"这是一场 Brass: Birmingham 四人桌测。你是座位 {SEAT_NAMES[seat]}，当前运河期。\n"
        f"现在轮到你行动（第 {beat} 拍，两行动回合中的决策请直接给出你现在要做的事）。\n"
        f"你的资金固定为 £{STARTING_FUNDS}（开局资金，演示中暂不精确扣费记账）。\n"
        f"你的手牌：{', '.join(hand)}。\n"
        f"公开市场：{format_market(market)}\n"
        f"近期公开行动：\n{hist}\n"
        f"请基于玩家视角决策；输出将被当作你的实际行动广播给其他玩家。"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="4-seat auto Brass table match")
    parser.add_argument("--beats", type=int, default=4, help="number of seat-actions to run")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT / "fixtures" / "birmingham" / "rules.full.md",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "sessions_table",
    )
    args = parser.parse_args()

    if not args.rules.exists():
        raise SystemExit(f"rules not found: {args.rules}")

    rng = random.Random(args.seed)
    hands = deal_hands(rng)
    market = random_market(rng)

    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_dir = args.out / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "match.log"

    def log(line: str) -> None:
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    log(f"=== table match {run_id} seed={args.seed} beats={args.beats} ===")
    for i, hand in enumerate(hands):
        log(f"[deal] seat {SEAT_NAMES[i]} hand={hand}")
    log(f"[deal] market={market}")
    log(f"[deal] starting funds=£{STARTING_FUNDS} (fixed)")

    settings = Settings()
    if not settings.deepseek_api_key:
        raise SystemExit("DEEPSEEK_API_KEY missing in .env")

    rules_text = args.rules.read_text(encoding="utf-8")
    log("[table] ingesting rules once...")
    ingest_store = SessionStore(run_dir / "rules_ingest")
    orch = Orchestrator(settings, LLMClient(settings), ingest_store)
    sid = orch.new_session(name="rules-ingest")
    orch.load_rules(sid, args.rules)
    card = ingest_store.read_rule_card(sid)
    assert card is not None
    card_dict = card.model_dump()
    (run_dir / "rule_card.json").write_text(
        json.dumps(card_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log("[table] rules ready")

    ctx = mp.get_context("spawn")
    in_qs = [ctx.Queue() for _ in range(4)]
    out_q: mp.Queue = ctx.Queue()
    procs = []
    llm_cfg = {
        "deepseek_api_key": settings.deepseek_api_key,
        "deepseek_base_url": settings.deepseek_base_url,
        "model_fast": settings.model_fast,
        # table demo: use fast model for advice too unless overridden
        "model_reasoning": settings.model_reasoning,
    }
    for seat in range(4):
        p = ctx.Process(
            target=player_process,
            args=(
                seat,
                in_qs[seat],
                out_q,
                str(run_dir / "players"),
                rules_text,
                card_dict,
                llm_cfg,
            ),
            daemon=True,
        )
        p.start()
        procs.append(p)

    try:
        wait_ready(out_q, 4)
        history: list[str] = []
        for beat in range(1, args.beats + 1):
            seat = (beat - 1) % 4
            log(f"\n--- beat {beat}: seat {SEAT_NAMES[seat]} acts ---")
            prompt = build_private_prompt(seat, hands[seat], market, beat, history)
            in_qs[seat].put({"type": "act", "text": prompt})
            result = drain_matching(out_q, {seat}, "action", timeout=900.0)[seat]
            action = result.get("action") or ""
            log(f"[action][{SEAT_NAMES[seat]}] {action}")
            public = (
                f"公开信息更新：座位 {SEAT_NAMES[seat]} 刚刚执行了如下行动（其顾问建议即为行动）：\n"
                f"{action}\n"
                f"市场仍为：{format_market(market)}。"
                f"你是旁观座位，只需记录公开信息，不要替对方补全私有细节，也不要追问对方手牌。"
            )
            history.append(f"{SEAT_NAMES[seat]}: {action[:200]}")
            others = {o for o in range(4) if o != seat}
            for other in others:
                in_qs[other].put({"type": "observe", "text": public})
            observed = drain_matching(out_q, others, "observed", timeout=900.0)
            for other in sorted(others):
                obs = observed[other]
                log(f"[observe][{SEAT_NAMES[other]}] {str(obs.get('ack', ''))[:120]}")
        log("\n=== match finished ===")
    finally:
        for q in in_qs:
            q.put({"type": "stop"})
        for p in procs:
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()

    log(f"log saved: {log_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
