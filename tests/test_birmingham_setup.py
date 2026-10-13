from board_game_agent.birmingham.setup import (
    MERCHANT_SLOTS_4P,
    MERCHANT_TILE_MIX_4P,
    build_draw_deck_4p,
    deal_merchant_tiles_4p,
    deal_opening_4p,
    setup_resource_markets,
)
import random


def test_draw_deck_is_64_and_has_no_oxford_card():
    deck = build_draw_deck_4p()
    assert len(deck) == 64
    assert all("Oxford" not in c for c in deck)
    assert deck.count("Location:Birmingham") == 3
    assert deck.count("Industry:Brewery") == 5


def test_resource_markets_follow_rulebook():
    m = setup_resource_markets()
    assert sum(1 for s in m.coal if s.price == 1 and not s.has_cube) == 1
    assert all(s.has_cube for s in m.coal if s.price != 1)
    assert [s.has_cube for s in m.iron if s.price == 1] == [False, False]


def test_merchant_tiles_cover_all_4p_slots():
    assert len(MERCHANT_TILE_MIX_4P) == 9
    assert len(MERCHANT_SLOTS_4P) == 9
    placed = deal_merchant_tiles_4p(random.Random(0))
    assert len(placed) == 9
    assert {p.tile for p in placed} == set(MERCHANT_TILE_MIX_4P)
    blanks = [p for p in placed if p.tile == "空白"]
    assert all(not p.has_beer for p in blanks)
    assert all(p.has_beer for p in placed if p.tile != "空白")


def test_deal_opening_includes_merchants():
    dealt = deal_opening_4p(random.Random(42))
    assert all(len(h) == 8 for h in dealt.hands)
    assert len(dealt.merchants) == 9
    assert len(dealt.draw_deck) == 28
