from __future__ import annotations
"""bot.py – расширенный набор стратегий для дуэльной игры.

Стратегии:

* **UltraAggressiveStrategy**   – «all‑in» rush: максимальный удар по врагу как можно раньше.
* **UltraDefensiveStrategy**    – «черепаха»: приоритет на оборону и экономию ресурсов.
* **EconomicBoomStrategy**      – экспансия нейтрала, затем сбалансированная армия.
* **AdaptiveOpponentStrategy**  – гибкая стратегия: подстраивает оборону/атаку под параметры врага,
  остальные средства вкладывает в развитие.

Каждый класс наследует :class:`Strategy` и принимает параметры через `__init__`.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

# Предполагаем, что базовый интерфейс Strategy расположен здесь
from autork.strategy import Strategy  # type: ignore

# ---------------------------------------------------------------------------
#                         U L T R A   A G G R E S S I V E
# ---------------------------------------------------------------------------

@dataclass
class UltraAggressiveStrategy(Strategy):
    """Сверх‑агрессивная rush‑стратегия.

    Parameters
    ----------
    reserve_gold: int
        Сколько золота оставлять нетронутым (буфер на содержание).
    attack_fraction: float
        Доля *доступного* золота, идущая в атаку (0‒1).
    expand_first_n: int
        Сколько клеток нейтрала захватить в первые ходы.
    scout_every: int
        Каждые `n` ходов тратить золото на разведку (0 – никогда).
    """

    sname = 'ultra_aggressive'  # имя стратегии

    reserve_gold: int = 0
    attack_fraction: float = 0.9
    expand_first_n: int = 1
    scout_every: int = 0

    _turn: int = 0
    _expanded: int = 0

    # ------------------------------------------------------------------ API
    def reset(self, initial_observation: Dict[str, Any]) -> None:  # noqa: D401
        self._turn = 0
        self._expanded = 0

    def step(self, obs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        self._turn += 1
        gold: int = obs["my"]["gold"]
        neutral: int = obs["neutral_territory"]
        prices = obs["prices"]

        cmd: Dict[str, Any] = {
            "expand": 0,
            "spend_attack": 0,
            "spend_defense": 0,
            "sell_attack": 0,
            "sell_defense": 0,
            "scout": False,
        }

        # --- разведка ---
        if self.scout_every and self._turn % self.scout_every == 0 and gold >= prices.get("scout", 0):
            cmd["scout"] = True
            gold -= prices.get("scout", 0)

        # --- ранняя экспансия ---
        if (
            self._expanded < self.expand_first_n
            and neutral > 0
            and gold >= prices.get("expand_next", 0)
        ):
            cmd["expand"] = 1
            gold -= prices.get("expand_next", 0)
            self._expanded += 1

        # --- rush‑атака ---
        spend_attack = max(0, int((gold - self.reserve_gold) * self.attack_fraction))
        cmd["spend_attack"] = spend_attack
        return cmd


# ---------------------------------------------------------------------------
#                         U L T R A   D E F E N S I V E
# ---------------------------------------------------------------------------

@dataclass
class UltraDefensiveStrategy(Strategy):
    """Сверх‑оборонительная стратегия («черепаха»).

    Parameters
    ----------
    defense_floor: int
        Минимум очков защиты, который нужно поддерживать.
    defense_focus_turns: int
        Сколько первых ходов почти всё золото идёт в защиту.
    save_for_upkeep: int
        Оставлять золота после трат (работает как резерв).
    expand_budget_ratio: float
        Доля оставшегося золота, которую можно тратить на расширение территории.
    """

    sname = "ultra_defensive"  # имя стратегии

    defense_floor: int = 20
    defense_focus_turns: int = 15
    save_for_upkeep: int = 5
    expand_budget_ratio: float = 0.4

    _turn: int = 0

    def reset(self, initial_observation: Dict[str, Any]) -> None:  # noqa: D401
        self._turn = 0

    def step(self, obs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        self._turn += 1
        gold: int = obs["my"]["gold"]
        my_def: int = obs["my"]["defense"]
        neutral: int = obs["neutral_territory"]
        prices = obs["prices"]

        cmd: Dict[str, Any] = {
            "expand": 0,
            "spend_attack": 0,
            "spend_defense": 0,
            "sell_attack": 0,
            "sell_defense": 0,
            "scout": False,
        }

        # --- приоритет: довести защиту до порога ---
        if my_def < self.defense_floor or self._turn <= self.defense_focus_turns:
            invest = max(0, gold - self.save_for_upkeep)
            if invest:
                cmd["spend_defense"] = invest
                gold -= invest

        # --- экспансия за счёт доли бюджета ---
        if neutral > 0 and gold > prices.get("expand_next", 0):
            budget = int(gold * self.expand_budget_ratio)
            cells = budget // prices.get("expand_next", 1)
            if cells:
                cmd["expand"] = cells
                gold -= cells * prices.get("expand_next", 0)

        # --- остаток тоже в защиту, если превышает резерв ---
        if gold - self.save_for_upkeep >= prices.get("buy_defense", 0):
            cmd["spend_defense"] += gold - self.save_for_upkeep
        return cmd


# ---------------------------------------------------------------------------
#                             E C O N O M I C   B O O M
# ---------------------------------------------------------------------------

@dataclass
class EconomicBoomStrategy(Strategy):
    """Экономическая стратегия: агрессивное расширение → баланс атака/защита."""
    sname = "economic_boom"  # имя стратегии

    neutral_threshold: int = 2
    expand_ratio: float = 0.6
    min_defense: int = 10
    balance_ratio: float = 0.3  # доля оставшегося золота на атаку
    scout_after_turn: int = 25

    _turn: int = 0

    def reset(self, initial_observation: Dict[str, Any]) -> None:  # noqa: D401
        self._turn = 0

    def step(self, obs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        self._turn += 1
        gold: int = obs["my"]["gold"]
        my_def: int = obs["my"]["defense"]
        neutral: int = obs["neutral_territory"]
        prices = obs["prices"]

        cmd: Dict[str, Any] = {
            "expand": 0,
            "spend_attack": 0,
            "spend_defense": 0,
            "sell_attack": 0,
            "sell_defense": 0,
            "scout": False,
        }

        # --- периодическая разведка ---
        if self._turn >= self.scout_after_turn and gold >= prices.get("scout", 0):
            cmd["scout"] = True
            gold -= prices.get("scout", 0)

        # --- Этап 1: расширение ---
        if neutral > self.neutral_threshold:
            budget = int(gold * self.expand_ratio)
            cells = budget // prices.get("expand_next", 1)
            if cells:
                cmd["expand"] = max(1, cells)
                gold -= cells * prices.get("expand_next", 0)

            # минимальная защита
            if my_def < self.min_defense and gold >= prices.get("buy_defense", 0):
                cmd["spend_defense"] = gold
                return cmd

        # --- Этап 2: баланс атака/защита ---
        spend_attack = int(gold * self.balance_ratio)
        cmd["spend_attack"] = spend_attack
        cmd["spend_defense"] = gold - spend_attack
        return cmd


# ---------------------------------------------------------------------------
#                        A D A P T I V E   O P P O N E N T
# ---------------------------------------------------------------------------

@dataclass
class AdaptiveOpponentStrategy(Strategy):
    """Гибкая стратегия, реагирующая на параметры оппонента.

    Логика:
    * Каждые `scout_every` ходов выполняет разведку для обновления данных.
    * Держит оборону на `defense_margin` выше текущей атаки противника.
    * Атаку развивает только если защита врага низкая (≤ `enemy_def_threshold`).
      На атаку выделяет не более `attack_budget_ratio` от оставшегося золота.
    * Оставшиеся средства вкладывает в развитие (колонизацию нейтрала).
    """
    sname = "adaptive_opponent"  # имя стратегии

    scout_every: int = 4
    defense_margin: int = 2
    enemy_def_threshold: int = 5
    attack_budget_ratio: float = 0.2

    _turn: int = 0

    def reset(self, initial_observation: Dict[str, Any]) -> None:  # noqa: D401
        self._turn = 0

    def step(self, obs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        self._turn += 1
        gold: int = obs["my"]["gold"]
        my_def: int = obs["my"]["defense"]
        neutral: int = obs["neutral_territory"]
        prices = obs["prices"]

        enemy_attack: int = obs["enemy"]["attack"]
        enemy_def: int = obs["enemy"]["defense"]

        cmd: Dict[str, Any] = {
            "expand": 0,
            "spend_attack": 0,
            "spend_defense": 0,
            "sell_attack": 0,
            "sell_defense": 0,
            "scout": False,
        }

        # --- периодическая разведка ---
        if self.scout_every and self._turn % self.scout_every == 0 and gold >= prices.get("scout", 0):
            cmd["scout"] = True
            gold -= prices.get("scout", 0)

        # --- обеспечить нужный уровень защиты ---
        desired_def = enemy_attack + self.defense_margin
        if my_def < desired_def and gold >= prices.get("buy_defense", 0):
            # Сколько очков защиты нужно купить (1 золото → 1 защита)
            need = desired_def - my_def
            invest = min(need, gold)
            cmd["spend_defense"] = invest
            gold -= invest
            my_def += invest

        # --- атака, только если защита врага низка ---
        if enemy_def <= self.enemy_def_threshold and gold > 0:
            atk_budget = int(gold * self.attack_budget_ratio)
            if atk_budget:
                cmd["spend_attack"] = atk_budget
                gold -= atk_budget

        # --- развитие: захват нейтрала оставшимися средствами ---
        if neutral > 0 and gold >= prices.get("expand_next", 0):
            cells = gold // prices.get("expand_next", 1)
            if cells:
                cmd["expand"] = cells
                gold -= cells * prices.get("expand_next", 0)

        return cmd
    
@dataclass
class AdaptiveOpponentStrategyV2(Strategy):
    """Продвинутая стратегия, оценивающая силу врага двумя способами:

    1. **Явная разведка** – чтение `enemy.attack` / `enemy.defense` раз в `scout_every` ходов.
    2. **Неявная индукция** – измерение фактически полученного урона:
       потеря собственных очков защиты и территории -> инференс скрытой атаки.

    Затем стратегия:
    * Держит защиту = *оценённая атака* + `defense_margin`.
    * Инвестирует в атаку лишь если оборона врага ≤ `enemy_def_threshold`.
    * Минимум `expand_floor_pct` бюджета всегда идёт на развитие.
    """
    sname = "adaptive_opponent_v2"  # имя стратегии

    # --- настройки тактики ---
    scout_every: int = 4  # период разведки
    defense_margin: int = 2  # сколько очков сверху держать
    enemy_def_threshold: int = 5  # считать оборону врага слабой
    attack_budget_ratio: float = 0.2  # доля остатка золота на атаку (если враг слаб)
    expand_floor_pct: int = 40  # % бюджета, который обязательно идёт на экспансию

    # --- настройки инференса урона ---
    infer_alpha: float = 0.5  # EMA сглаживание наблюд. урона
    defense_loss_weight: float = 1.0  # вклад потери защиты в оценку атаки
    territory_loss_weight: float = 1.0  # вклад потери клеток

    # --- внутреннее состояние ---
    _turn: int = 0
    _prev_def: Optional[int] = None
    _prev_land: Optional[int] = None
    _ema_obs_attack: float = 0.0

    # ------------------------------------------------------------------ API
    def reset(self, initial_observation: Dict[str, Any]) -> None:  # noqa: D401
        self._turn = 0
        self._prev_def = None
        self._prev_land = None
        self._ema_obs_attack = 0.0

    def _infer_attack_from_damage(
        self,
        my_def: int,
        my_land: int,
    ) -> float:
        """Вычислить атаку врага на основании наших потерь за ход."""
        if self._prev_def is None or self._prev_land is None:
            return 0.0
        def_loss = max(0, self._prev_def - my_def)
        land_loss = max(0, self._prev_land - my_land)
        return (
            def_loss * self.defense_loss_weight
            + land_loss * self.territory_loss_weight
        )

    def step(self, obs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        self._turn += 1
        gold: int = obs["my"]["gold"]
        my_def: int = obs["my"]["defense"]
        my_land: int = obs["my"].get("territory", 0)
        neutral: int = obs.get("neutral_territory", 0)
        prices = obs["prices"]

        enemy_attack: int = obs["enemy"]["attack"]
        enemy_def: int = obs["enemy"]["defense"]

        # --- инференс скрытой атаки ---
        observed_attack = self._infer_attack_from_damage(my_def, my_land)
        # EMA сглаживание
        self._ema_obs_attack = (
            self.infer_alpha * observed_attack + (1 - self.infer_alpha) * self._ema_obs_attack
        )

        # --- итоговая оценка атаки врага ---
        estimated_attack = max(enemy_attack, self._ema_obs_attack)

        cmd: Dict[str, Any] = {
            "expand": 0,
            "spend_attack": 0,
            "spend_defense": 0,
            "sell_attack": 0,
            "sell_defense": 0,
            "scout": False,
        }

        # --- разведываем при необходимости ---
        if self.scout_every and self._turn % self.scout_every == 0 and gold >= prices.get("scout", 0):
            cmd["scout"] = True
            gold -= prices.get("scout", 0)

        # --- обеспечить достаточную защиту ---
        desired_def = int(estimated_attack) + self.defense_margin
        if my_def < desired_def and gold >= prices.get("buy_defense", 0):
            need = desired_def - my_def
            invest = min(need, gold)
            cmd["spend_defense"] = invest
            gold -= invest
            my_def += invest  # обновить локальную переменную

        # --- атака, только если враг слаб ---
        if enemy_def <= self.enemy_def_threshold and gold > 0:
            atk_budget = int(gold * self.attack_budget_ratio)
            if atk_budget > 0:
                cmd["spend_attack"] = atk_budget
                gold -= atk_budget

        # --- минимум на экспансию ---
        expand_budget_min = int(gold * self.expand_floor_pct / 100)
        if neutral and gold >= prices.get("expand_next", 0):
            cells = expand_budget_min // prices.get("expand_next", 1)
            if cells > 0:
                cmd["expand"] = cells
                gold -= cells * prices.get("expand_next", 0)

        # --- сохранить состояние для следующего шага ---
        self._prev_def = my_def
        self._prev_land = my_land

        return cmd



# -------------------------------------------------------------
# Вспомогательная микс‑функция инференса скрытой атаки (EMA)
# -------------------------------------------------------------

def _ema(prev: float, new: float, alpha: float) -> float:
    return alpha * new + (1 - alpha) * prev


def _observe_attack(
    prev_def: Optional[int],
    prev_land: Optional[int],
    cur_def: int,
    cur_land: int,
    w_def: float = 1.0,
    w_land: float = 1.0,
) -> float:
    if prev_def is None or prev_land is None:
        return 0.0
    return max(0, (prev_def - cur_def) * w_def + (prev_land - cur_land) * w_land)

# ---------------------------------------------------------------------------
#                         U L T R A   D E F E N S I V E   v2
# ---------------------------------------------------------------------------

@dataclass
class UltraDefensiveStrategyV2(Strategy):
    """«Черепаха v2»: адаптивная оборонительная стратегия.

    * Поддерживает защиту ≥ оценённая_атака_врага + `def_margin`.
    * При низком золоте *распродаёт* избыточные очки защиты, превышающие
      `def_margin + overshoot_sell`, чтобы оплачивать содержание и расширение.
    * При слабой обороне врага (≤ `enemy_def_weak`) начинает накапливать **атаку**
      (но не более `atk_budget_ratio` от оставшегося золота).
    * Обязательно тратит не менее `expand_floor_pct` оставшегося бюджета на
      колонизацию нейтрала.
    """

    sname = "turtle_v2"  # имя стратегии

    # --- тактические параметры ---
    def_margin: int = 2
    overshoot_sell: int = 5   # запас DEF, после которого продаём лишнее
    enemy_def_weak: int = 4   # порог слабости брони врага
    atk_budget_ratio: float = 0.15
    expand_floor_pct: int = 30  # минимум на экспансию

    # --- инференс ---
    scout_every: int = 6
    ema_alpha: float = 0.5

    # --- внутреннее состояние ---
    _turn: int = 0
    _ema_attack: float = 0.0
    _prev_def: Optional[int] = None
    _prev_land: Optional[int] = None

    # -------------------------------------------------- API
    def reset(self, initial_observation: Dict[str, Any]) -> None:  # noqa: D401
        self._turn = 0
        self._ema_attack = 0.0
        self._prev_def = None
        self._prev_land = None

    def step(self, obs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        self._turn += 1
        gold: int = obs["my"]["gold"]
        my_def: int = obs["my"]["defense"]
        my_land: int = obs["my"]["territory"]
        neutral: int = obs["neutral_territory"]
        prices = obs["prices"]

        # --- оценка атаки врага ---
        enemy_attack_vis = obs["enemy"].get("attack", 0)
        observed = _observe_attack(self._prev_def, self._prev_land, my_def, my_land)
        self._ema_attack = _ema(self._ema_attack, observed, self.ema_alpha)
        est_attack = max(enemy_attack_vis, self._ema_attack)

        cmd: Dict[str, Any] = {
            "expand": 0,
            "spend_attack": 0,
            "spend_defense": 0,
            "sell_attack": 0,
            "sell_defense": 0,
            "scout": False,
        }

        # --- разведка по таймеру ---
        if self.scout_every and self._turn % self.scout_every == 0 and gold >= prices["scout"]:
            cmd["scout"] = True
            gold -= prices["scout"]

        # --- целевой уровень защиты ---
        target_def = int(est_attack) + self.def_margin
        if my_def < target_def:
            need = min(target_def - my_def, gold)
            cmd["spend_defense"] = need
            gold -= need
            my_def += need
        else:
            # слишком много защиты? продаём, если не хватает золота
            excess = my_def - target_def
            if excess > self.overshoot_sell and gold < prices["expand_next"]:
                sell_units = min(excess - self.overshoot_sell, my_def // 4)
                cmd["sell_defense"] = sell_units
                gold += sell_units * (prices["buy_defense"] // 2)
                my_def -= sell_units

        # --- слабая броня врага → немного атаки ---
        enemy_def = obs["enemy"].get("defense", 0)
        if enemy_def <= self.enemy_def_weak and gold > 0:
            atk_budget = int(gold * self.atk_budget_ratio)
            if atk_budget >= prices["buy_attack"]:
                cmd["spend_attack"] = atk_budget
                gold -= atk_budget

        # --- минимум бюджета на нейтрал ---
        if neutral and gold >= prices["expand_next"]:
            to_expand = max(1, int(gold * self.expand_floor_pct / 100) // prices["expand_next"])
            cmd["expand"] = to_expand
            gold -= to_expand * prices["expand_next"]

        # --- сохранить текущие показатели ---
        self._prev_def = my_def
        self._prev_land = my_land
        return cmd

# ---------------------------------------------------------------------------
#                             E C O N O M I C   B O O M   v2
# ---------------------------------------------------------------------------

@dataclass
class EconomicBoomStrategyV2(Strategy):
    """Экономическая стратегия v2: быстрая экспансия с адаптивной обороной.

    * Расширяется, пока нейтрал есть, **но** держит защиту ≥ атака_врага+`def_margin`.
    * При угрозе продаёт лишнюю атаку (если накоплена) или часть экспансии
      замораживает в пользу обороны.
    * После окончания нейтрала перераспределяет доход 60/40 между атакой и обороной,
      но продолжает следить за параметрами врага.
    """

    sname = "economic_boom_v2"  # имя стратегии

    # --- параметры тактики ---
    def_margin: int = 1
    scout_every: int = 5
    expand_ratio: float = 0.75  # fraction of gold to spend on expansion in phase 1
    post_expand_atk_share: float = 0.6  # после нейтрала доля на атаку
    sell_attack_threshold: int = 8  # если моя атака настолько превышает броню врага — распродать
    ema_alpha: float = 0.4

    _turn: int = 0
    _ema_attack: float = 0.0
    _prev_def: Optional[int] = None
    _prev_land: Optional[int] = None

    # -------------------------------------------------- API
    def reset(self, initial_observation: Dict[str, Any]) -> None:  # noqa: D401
        self._turn = 0
        self._ema_attack = 0.0
        self._prev_def = None
        self._prev_land = None

    def step(self, obs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        self._turn += 1
        gold: int = obs["my"]["gold"]
        my_def: int = obs["my"]["defense"]
        my_atk: int = obs["my"]["attack"]
        my_land: int = obs["my"]["territory"]
        neutral: int = obs["neutral_territory"]
        prices = obs["prices"]

        enemy_attack_vis = obs["enemy"].get("attack", 0)
        enemy_def_vis = obs["enemy"].get("defense", 0)
        observed = _observe_attack(self._prev_def, self._prev_land, my_def, my_land)
        self._ema_attack = _ema(self._ema_attack, observed, self.ema_alpha)
        est_enemy_attack = max(enemy_attack_vis, self._ema_attack)

        cmd: Dict[str, Any] = {
            "expand": 0,
            "spend_attack": 0,
            "spend_defense": 0,
            "sell_attack": 0,
            "sell_defense": 0,
            "scout": False,
        }

        # --- разведка периодически ---
        if self.scout_every and self._turn % self.scout_every == 0 and gold >= prices["scout"]:
            cmd["scout"] = True
            gold -= prices["scout"]

        # --- обеспечить минимальную оборону ---
        target_def = int(est_enemy_attack) + self.def_margin
        if my_def < target_def and gold >= prices["buy_defense"]:
            need = min(target_def - my_def, gold)
            cmd["spend_defense"] = need
            gold -= need
            my_def += need

        # --- ФАЗА 1: ещё есть нейтрал ---
        if neutral > 0:
            # трата на экспансию
            budget_exp = int(gold * self.expand_ratio)
            cells = budget_exp // prices["expand_next"]
            if cells > 0:
                cmd["expand"] = cells
                gold -= cells * prices["expand_next"]

            # немного атаки, если враг слаб
            if enemy_def_vis and enemy_def_vis < my_atk:
                atk_budget = min(int(gold * 0.25), gold)
                if atk_budget >= prices["buy_attack"]:
                    cmd["spend_attack"] = atk_budget
                    gold -= atk_budget
        else:
            # ФАЗА 2: нейтрал кончился → распределяем 60/40
            atk_budget = int(gold * self.post_expand_atk_share)
            cmd["spend_attack"] = atk_budget
            cmd["spend_defense"] += gold - atk_budget
            gold = 0

        # --- распродажа избыточной атаки (экономия на содержании) ---
        if enemy_def_vis and my_atk - enemy_def_vis > self.sell_attack_threshold and my_atk > 0:
            sell_units = (my_atk - enemy_def_vis - self.sell_attack_threshold) // 2
            if sell_units > 0:
                cmd["sell_attack"] = sell_units

        # --- сохранить историю ---
        self._prev_def = my_def
        self._prev_land = my_land
        return cmd

