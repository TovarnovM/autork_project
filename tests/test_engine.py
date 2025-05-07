import pytest

# Project imports – support both package and local layouts
try:
    from autork.engine import PlayerState, Engine
    from autork.config import GameSettings
except ImportError:  # pragma: no cover – fallback for local execution
    from engine import PlayerState, Engine  # type: ignore
    from config import GameSettings  # type: ignore


class DummyStrategy:
    """A minimal do‑nothing strategy useful for deterministic unit tests."""

    def reset(self, observation):
        pass

    def step(self, observation):
        # Return an empty command dict – the engine will treat it as ‘skip turn’.
        return {}


# ---------------------------------------------------------------------------
# PlayerState unit tests
# ---------------------------------------------------------------------------

def test_income():
    cfg = GameSettings()
    p = PlayerState(cfg)
    p.territory = 25
    assert p.income() == 25


def test_upkeep_auto_demobilise():
    cfg = GameSettings(START_ATTACK=3, START_DEFENSE=2, START_GOLD=2)
    p = PlayerState(cfg)
    # Preconditions
    assert p.attack == 3 and p.defense == 2 and p.gold == 2
    # Apply upkeep (cost = 5) ⇒ gold negative ⇒ units disband starting with attack
    p.apply_upkeep()
    assert p.gold == 0, "Gold should never remain negative after upkeep logic"
    assert p.attack == 0, "Attack units are dismissed first to cover deficit"
    assert p.defense == 2, "Defense untouched after all attack removed"


def test_expand_price_and_payment():
    cfg = GameSettings()
    cfg.EXPAND_BASE = 10
    cfg.EXPAND_STEP = 1
    p = PlayerState(cfg)
    # First three expansion prices 10, 11, 12 by default
    assert p.expand_price() == 10
    assert p.expand_price(extra=1) == 11  # simulate second cell in same turn

    p.gold = 50
    bought = p.pay_for_expands(3)
    assert bought == 3
    assert p.gold == 17  # 50 - (10+11+12)
    assert p.pending_expands == 3

    # Not enough money for next batch
    bought = p.pay_for_expands(3)
    # Gold is only 17 → can afford 13 & 14 (total 27) – 1 actually, so 1
    assert bought == 1


def test_buy_attack_and_defense():
    cfg = GameSettings()
    p = PlayerState(cfg)
    p.gold = 60
    spent = p.buy_attack(60)  # prices 20, 22, 24 – only 2 units within 60
    assert spent == 42
    assert p.attack == cfg.START_ATTACK + 2
    assert p.gold == 18

    spent_def = p.buy_defense(18)  # prices 13, 14 – only 1 unit
    assert spent_def == 13
    assert p.defense == cfg.START_DEFENSE + 1
    assert p.gold == 5


# ---------------------------------------------------------------------------
# Engine core mechanic tests (allocate_neutral, resolve_combat, winner logic)
# ---------------------------------------------------------------------------


def _fresh_engine():
    """Utility to get a reset Engine with dummy strategies and muted trace."""
    return Engine(DummyStrategy(), DummyStrategy(), trace=lambda *_: None)


def test_allocate_neutral_contested():
    eng = _fresh_engine()
    eng.neutral_territory = 5
    eng.p1.pending_expands = 3
    eng.p2.pending_expands = 3

    eng._allocate_neutral()

    # All 3 contested → none granted, neutral remains 5
    assert eng.p1.territory == eng.cfg.START_TERRITORY
    assert eng.p2.territory == eng.cfg.START_TERRITORY
    assert eng.neutral_territory == 5


def test_allocate_neutral_unique():
    eng = _fresh_engine()
    eng.neutral_territory = 4
    eng.p1.pending_expands = 3  # wants 3 unique
    eng.p2.pending_expands = 0

    eng._allocate_neutral()

    assert eng.p1.territory == eng.cfg.START_TERRITORY + 3
    assert eng.neutral_territory == 1  # 4 - 3 = 1 left


def test_resolve_combat_shift_territory():
    eng = _fresh_engine()
    # set forces
    eng.p1.attack = 12
    eng.p1.defense = 5
    eng.p2.attack = 5
    eng.p2.defense = 10
    eng.p1.territory = 30
    eng.p2.territory = 30
    eng.neutral_territory = 0

    eng._resolve_combat()

    assert eng.p1.territory == 30  # no losses
    assert eng.p2.territory == 28  # lost 2 cells
    assert eng.neutral_territory == 2  # captured cells become neutral


def test_winner_detection_by_territory():
    eng = _fresh_engine()
    eng.p1.territory = 0
    eng.p2.territory = 10

    assert eng._check_winner() == "player2"

    eng.p2.territory = 0
    assert eng._check_winner() == "draw"


def test_winner_detection_by_gold_on_timeout():
    eng = _fresh_engine()
    eng.p1.gold = 100
    eng.p2.gold = 50
    # Both still have territory, simulate end‑of‑game flag
    assert eng._check_winner(is_end=True) == "player1"
