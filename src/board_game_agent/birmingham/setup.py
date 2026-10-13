"""Brass: Birmingham setup helpers (4-player).

What is randomized at setup:
- Draw-deck shuffle → hands / opening discards
- Merchant tiles (棉 / 制造 / 陶 / 全能 / 空白) onto merchant spaces

What is fixed by the rulebook (not a free random market):
- Starting funds £17
- Coal / iron cube placement on the price tracks
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# --- Draw deck (64 Location + Industry cards). Wilds stay face-up off the deck. ---

LOCATION_COUNTS_4P: dict[str, int] = {
    "Belper": 2,
    "Derby": 3,
    "Leek": 2,
    "Stoke-on-Trent": 3,
    "Stone": 2,
    "Uttoxeter": 2,
    "Stafford": 2,
    "Burton-on-Trent": 2,
    "Cannock": 2,
    "Tamworth": 1,
    "Walsall": 1,
    "Coalbrookdale": 3,
    "Dudley": 2,
    "Kidderminster": 2,
    "Wolverhampton": 2,
    "Worcester": 2,
    "Birmingham": 3,
    "Coventry": 3,
    "Nuneaton": 1,
    "Redditch": 1,
}

INDUSTRY_COUNTS_4P: dict[str, int] = {
    "Iron Works": 4,
    "Coal Mine": 3,
    "Manufacturer / Cotton Mill": 8,
    "Pottery": 3,
    "Brewery": 5,
}

# Coal / Iron Market price spaces (cheap → expensive). Setup is fixed by rules.
COAL_MARKET_PRICES: list[int] = [1, 1, 2, 3, 4, 5, 7, 8]
IRON_MARKET_PRICES: list[int] = [1, 1, 2, 3, 4, 5]

STARTING_FUNDS = 17
HAND_SIZE = 8

# Merchant tile kinds (Chinese labels used in prompts).
# Mix for 4 players (verified against independent engine data / component mix).
MERCHANT_TILE_MIX_4P: list[str] = [
    "棉造陶",  # any / all three sell icons
    "棉造陶",
    "棉",
    "棉",
    "造",  # manufactured goods
    "造",
    "陶",
    "空白",
    "空白",
]

# Merchant spaces for 4p: slot counts accumulate by player-count groups.
# Order is deal order within each location's slots.
MERCHANT_SLOTS_4P: list[tuple[str, str]] = [
    # 2p spaces
    ("Shrewsbury", "啤酒奖励: +4 VP"),
    ("Gloucester", "啤酒奖励: Develop 1"),
    ("Gloucester", "啤酒奖励: Develop 1"),
    ("Oxford", "啤酒奖励: Income +2 spaces"),
    ("Oxford", "啤酒奖励: Income +2 spaces"),
    # 3p adds
    ("Warrington", "啤酒奖励: £5"),
    ("Warrington", "啤酒奖励: £5"),
    # 4p adds
    ("Nottingham", "啤酒奖励: +3 VP"),
    ("Nottingham", "啤酒奖励: +3 VP"),
]

GOODS_ZH = {
    "棉": "Cotton Mill（棉）",
    "造": "Manufacturer（制造）",
    "陶": "Pottery（陶）",
    "棉造陶": "Cotton / Manufacturer / Pottery（全能）",
    "空白": "空白（不可卖货；无商人啤酒）",
}


def build_draw_deck_4p() -> list[str]:
    deck: list[str] = []
    for name, n in LOCATION_COUNTS_4P.items():
        deck.extend([f"Location:{name}"] * n)
    for name, n in INDUSTRY_COUNTS_4P.items():
        deck.extend([f"Industry:{name}"] * n)
    if len(deck) != 64:
        raise ValueError(f"4p draw deck must be 64 cards, got {len(deck)}")
    return deck


@dataclass
class MarketSpace:
    price: int
    has_cube: bool

    def label(self) -> str:
        goods = "有货" if self.has_cube else "空"
        return f"£{self.price}({goods})"


@dataclass
class ResourceMarkets:
    coal: list[MarketSpace]
    iron: list[MarketSpace]

    def describe(self) -> str:
        coal_s = " → ".join(s.label() for s in self.coal)
        iron_s = " → ".join(s.label() for s in self.iron)
        return (
            "煤市场轨道（规则固定摆法，从便宜到贵）："
            f"{coal_s}。空市仍可买 £8。\n"
            "铁市场轨道（规则固定摆法，从便宜到贵）："
            f"{iron_s}。空市仍可买 £6。"
        )


def setup_resource_markets() -> ResourceMarkets:
    """Rulebook fixed setup: coal leaves one £1 open; iron leaves both £1 open.

    Which of the two coal £1 spaces is open does not matter strategically beyond
    identical price; we always open the first £1 for determinism.
    """
    coal = [MarketSpace(price=p, has_cube=True) for p in COAL_MARKET_PRICES]
    for i, s in enumerate(coal):
        if s.price == 1:
            coal[i].has_cube = False
            break
    iron = [MarketSpace(price=p, has_cube=(p != 1)) for p in IRON_MARKET_PRICES]
    return ResourceMarkets(coal=coal, iron=iron)


@dataclass
class MerchantPlacement:
    location: str
    tile: str
    beer_bonus: str
    has_beer: bool

    def describe(self) -> str:
        beer = "有1啤酒" if self.has_beer else "无啤酒"
        return f"{self.location}: {GOODS_ZH[self.tile]}（{beer}；{self.beer_bonus}）"


def deal_merchant_tiles_4p(rng: random.Random) -> list[MerchantPlacement]:
    """Shuffle merchant tiles and place one on each 4p merchant slot."""
    if len(MERCHANT_TILE_MIX_4P) != len(MERCHANT_SLOTS_4P):
        raise ValueError("merchant tile count must match 4p slot count")
    tiles = list(MERCHANT_TILE_MIX_4P)
    rng.shuffle(tiles)
    out: list[MerchantPlacement] = []
    for (location, bonus), tile in zip(MERCHANT_SLOTS_4P, tiles, strict=True):
        out.append(
            MerchantPlacement(
                location=location,
                tile=tile,
                beer_bonus=bonus,
                has_beer=(tile != "空白"),
            )
        )
    return out


def describe_merchants(placements: list[MerchantPlacement]) -> str:
    lines = ["商人市场（随机瓷砖 → 固定商人位；决定棉/造/陶能卖到哪里）："]
    by_loc: dict[str, list[MerchantPlacement]] = {}
    for p in placements:
        by_loc.setdefault(p.location, []).append(p)
    for loc, items in by_loc.items():
        joined = "；".join(
            f"{GOODS_ZH[i.tile]} / {'有啤酒' if i.has_beer else '无啤酒'}" for i in items
        )
        lines.append(f"- {loc}: {joined}（{items[0].beer_bonus}）")
    return "\n".join(lines)


@dataclass
class DealtSetup:
    hands: list[list[str]]
    opening_discards: list[str]
    draw_deck: list[str]
    resource_markets: ResourceMarkets
    merchants: list[MerchantPlacement]


def deal_opening_4p(rng: random.Random) -> DealtSetup:
    """Shuffle draw deck + merchant tiles; deal hands; apply fixed coal/iron tracks."""
    deck = build_draw_deck_4p()
    rng.shuffle(deck)
    hands: list[list[str]] = []
    opening_discards: list[str] = []
    for _ in range(4):
        hand = [deck.pop() for _ in range(HAND_SIZE)]
        discard = deck.pop()
        hands.append(hand)
        opening_discards.append(discard)
    return DealtSetup(
        hands=hands,
        opening_discards=opening_discards,
        draw_deck=deck,
        resource_markets=setup_resource_markets(),
        merchants=deal_merchant_tiles_4p(rng),
    )
