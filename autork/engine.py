"""duel_game.engine – основной игровой движок

Изменения:
1. Движок допускает передачу альтернативного объекта настроек (`GameSettings`).
2. Исправлена логика боя: забранная силами атаки территория переходит в нейтральный фонд.
3. Полностью переписана механика колонизации нейтрала.
   * Стратегии отдают **заявки** (сколько клеток купить).
   * Золото списывается сразу за каждую заявку.
   * Затем заявки обрабатываются **симультанно**:
       - Если обе стороны претендуют на одни и те же клетки, они обе платят, 
         но эти клетки остаются нейтральными ("оспоренные").
       - Оставшиеся свободные клетки распределяются между заявителями,
         пока не исчерпается нейтрал.

В результате ни одна стратегия не получает преимущества от порядка вызовов.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from .config import settings as _default_settings, GameSettings

# ---------------------------------------------------------
Command = Dict[str, Any]
Observation = Dict[str, Any]
TraceFn = Callable[[str], None]


class PlayerState:
    """Хранит состояние игрока и ссылается на объект настроек."""

    def __init__(self, cfg: GameSettings):
        self.cfg = cfg
        self.gold: int = cfg.START_GOLD
        self.territory: int = cfg.START_TERRITORY
        self.attack: int = cfg.START_ATTACK
        self.defense: int = cfg.START_DEFENSE
        self.expanded_total: int = 0  # купленные (полученные) клетки за всё время
        self.pending_expands: int = 0  # заявки на текущий ход – сколько клеток куплено
        self.has_enemy_intel: bool = False

    # ---------- экономика ----------
    def income(self) -> int:
        return self.territory * self.cfg.GOLD_PER_LAND

    def upkeep_cost(self) -> int:
        return self.attack * self.cfg.MAINT_ATK + self.defense * self.cfg.MAINT_DEF

    def apply_upkeep(self) -> None:
        self.gold -= self.upkeep_cost()
        if self.gold >= 0:
            return
        deficit = -self.gold
        while deficit > 0 and (self.attack or self.defense):
            if self.attack:
                self.attack -= 1
                self.gold += self.cfg.MAINT_ATK
                deficit -= self.cfg.MAINT_ATK
            elif self.defense:
                self.defense -= 1
                self.gold += self.cfg.MAINT_DEF
                deficit -= self.cfg.MAINT_DEF
        if self.gold < 0:
            self.gold = 0

    # ---------- покупки ----------
    def expand_price(self, extra: int = 0) -> int:
        """Цена очередной клетки с учётом *extra* уже запрошенных в этом ходу."""
        return self.cfg.EXPAND_BASE + self.cfg.EXPAND_STEP * (self.expanded_total + extra)

    def pay_for_expands(self, wanted: int) -> int:
        """Пытается купить *wanted* клеток. Всегда списывает золото **даже** если
        клетки потом не будут переданы (оспорены или кончился нейтрал).

        Возвращает количество **заявленных** клеток (может быть меньше wanted),
        ограниченное текущим запасом золота.
        """
        bought = 0
        while bought < wanted:
            cost = self.expand_price(extra=bought)
            if self.gold < cost:
                break
            self.gold -= cost
            bought += 1
        self.pending_expands = bought
        return bought

    # динамические цены на атаку/защиту
    def _attack_price(self) -> int:
        return self.cfg.ATK_BASE + self.cfg.ATK_K * self.attack

    def _defense_price(self) -> int:
        return self.cfg.DEF_BASE + self.cfg.DEF_K * self.defense

    def buy_attack(self, gold_limit: int) -> int:
        spent = 0
        while gold_limit - spent >= self._attack_price():
            price = self._attack_price()
            self.attack += 1
            spent += price
        self.gold -= spent
        return spent

    def buy_defense(self, gold_limit: int) -> int:
        spent = 0
        while gold_limit - spent >= self._defense_price():
            price = self._defense_price()
            self.defense += 1
            spent += price
        self.gold -= spent
        return spent

    def _refund_attack(self, units: int) -> int:
        units = max(0, min(units, self.attack))
        refund = units * (self.cfg.ATK_BASE // 2)
        self.attack -= units
        self.gold  += refund
        return refund

    def _refund_defense(self, units: int) -> int:
        units = max(0, min(units, self.defense))
        refund = units * (self.cfg.DEF_BASE // 2)
        self.defense -= units
        self.gold   += refund
        return refund
    
    

class Engine:
    """Оркестратор матча (бот vs бот)."""

    def __init__(
        self,
        strat_a,
        strat_b,
        *,
        trace: TraceFn | None = print,
        game_settings: GameSettings | None = None,
    ) -> None:
        self.cfg: GameSettings = game_settings or _default_settings
        self.s1 = strat_a
        self.s2 = strat_b
        self.trace: TraceFn = trace or (lambda *_: None)
        # Сразу готовим место под историю и состояние
        self.reset()

    def _render(self):
        pass

    # ---------- служебные ----------
    def reset(self) -> None:
        """Полный сброс матча: ходы, нейтрал, игроки, история."""
        self.turn: int = 0
        self.neutral_territory: int = self.cfg.NEUTRAL_TERRITORY
        self.p1 = PlayerState(self.cfg)
        self.p2 = PlayerState(self.cfg)
        self.history: List[Dict[str, Any]] = []
        self._record_snapshot()  # начальное состояние (turn=0)

    def _record_snapshot(self) -> None:
        self.history.append(
            {
                "turn": self.turn,
                "neutral": self.neutral_territory,
                "p1": {
                    "territory": self.p1.territory,
                    "gold": self.p1.gold,
                    "attack": self.p1.attack,
                    "defense": self.p1.defense,
                },
                "p2": {
                    "territory": self.p2.territory,
                    "gold": self.p2.gold,
                    "attack": self.p2.attack,
                    "defense": self.p2.defense,
                },
            }
        )

    # --------------------------------------------------
    def run(self) -> Dict[str, Any]:
        self.reset()
        self.trace("=== DUEL GAME START ===")
        self.s1.reset(self._observation(1))
        self.s2.reset(self._observation(2))

        self._render()
        
        while self.turn < self.cfg.MAX_TURNS:
            if not self._handle_gui_events():
                break

            self.turn += 1
            self.trace(f"\n--- TURN {self.turn} ---")
            self._play_turn()
            self._render()
            if self._winner_declared():
                break
        result = self._result(is_end=True)
        self.trace("\n=== RESULT ===")
        self.trace(result)
        self._final_render()
        return result
    
    def _handle_gui_events(self):
        return True

    def _final_render(self):
        pass

    # --------------------------------------------------
    def _play_turn(self):
        # 1. Экономика и содержание
        for pid, pl in enumerate((self.p1, self.p2), start=1):
            pl.gold += pl.income()
            pl.apply_upkeep()
            self.trace(
                f"P{pid} income=+{pl.income()} upkeep=-{pl.upkeep_cost()} gold={pl.gold}"
            )

        # 2. Подготовить наблюдения и запросить команды
        obs1, prices1 = self._prepare_obs(self.p1, self.p2)
        obs2, prices2 = self._prepare_obs(self.p2, self.p1)

        cmd1 = self._safe_step(self.s1, obs1)
        cmd2 = self._safe_step(self.s2, obs2)

        # 3. Обработать команды (списать деньги, но **не** менять нейтрал)
        self._apply_commands(self.p1, cmd1, prices1, pid=1)
        self._apply_commands(self.p2, cmd2, prices2, pid=2)

        # 4. Распределить нейтральную территорию с учётом конфликтов
        self._allocate_neutral()

        # 5. Сражение
        self._resolve_combat()

        # 6. Обновить разведку
        self.p1.has_enemy_intel = cmd1.get("scout", False)
        self.p2.has_enemy_intel = cmd2.get("scout", False)

    # ---------- наблюдения ----------
    def _prepare_obs(self, me: PlayerState, enemy: PlayerState) -> Tuple[Observation, Dict[str, int]]:
        prices = {
            "expand_next": me.expand_price(),
            "buy_attack": me._attack_price(),
            "buy_defense": me._defense_price(),
            "scout": self.cfg.SCOUT_COST,
        }
        obs: Observation = {
            "turn": self.turn,
            "my": {
                "gold": me.gold,
                "territory": me.territory,
                "attack": me.attack,
                "defense": me.defense,
            },
            "enemy": {"territory": enemy.territory}
            | (
                {
                    "gold": enemy.gold,
                    "attack": enemy.attack,
                    "defense": enemy.defense,
                }
                if me.has_enemy_intel
                else {}
            ),
            "neutral_territory": self.neutral_territory,
            "prices": prices,
            "limits": {"gold": me.gold},
        }
        return obs, prices

    def _observation(self, pid: int) -> Observation:
        obs, _ = (
            self._prepare_obs(self.p1, self.p2)
            if pid == 1
            else self._prepare_obs(self.p2, self.p1)
        )
        return obs

    # ---------- команды ----------
    def _safe_step(self, strat, obs: Observation) -> Command:
        try:
            res = strat.step(obs)
            if not isinstance(res, dict):
                raise TypeError("Strategy.step must return dict")
            return res
        except Exception as exc:
            self.trace(f"[ERROR] Strategy {strat} crashed: {exc}")
            return {}

    def _apply_commands(
        self,
        player: PlayerState,
        cmd: Command,
        prices: Dict[str, int],
        *,
        pid: int,
    ) -> None:
        
        sell_atk  = max(0, int(cmd.get("sell_attack", 0)))
        if sell_atk:
            ref = player._refund_attack(sell_atk)
            self.trace(f"P{pid} sell {sell_atk} atk (+{ref}g)")

        sell_def  = max(0, int(cmd.get("sell_defense", 0)))
        if sell_def:
            ref = player._refund_defense(sell_def)
            self.trace(f"P{pid} sell {sell_def} def (+{ref}g)")

        # ----- expand (только деньги + заявка) -----
        want_expand = max(0, int(cmd.get("expand", 0)))
        bought = player.pay_for_expands(want_expand)
        if bought < want_expand:
            self.trace(f"P{pid} expand limited by gold to {bought}/{want_expand}")

        # ----- scout -----
        if cmd.get("scout", False):
            if player.gold >= self.cfg.SCOUT_COST:
                player.gold -= self.cfg.SCOUT_COST
                self.trace(f"P{pid} scout (-{self.cfg.SCOUT_COST}g)")
            else:
                self.trace(f"P{pid} cannot afford scout")

        # ----- attack / defense -----
        atk_spend = max(0, int(cmd.get("spend_attack", 0)))
        atk_spend = min(atk_spend, player.gold)
        real_atk = player.buy_attack(atk_spend)
        if real_atk < atk_spend:
            self.trace(f"P{pid} atk spend trimmed to {real_atk}/{atk_spend}")

        def_spend = max(0, int(cmd.get("spend_defense", 0)))
        def_spend = min(def_spend, player.gold)
        real_def = player.buy_defense(def_spend)
        if real_def < def_spend:
            self.trace(f"P{pid} def spend trimmed to {real_def}/{def_spend}")

        # неведомые ключи
        for k in cmd.keys() - {"sell_attack", "sell_defense", "expand", "spend_attack", "spend_defense", "scout"}:
            self.trace(f"P{pid} unknown key '{k}' ignored")

    # ---------- распределение нейтрала ----------
    def _allocate_neutral(self):
        a1 = self.p1.pending_expands
        a2 = self.p2.pending_expands
        N = self.neutral_territory

        # Оспоренные клетки – первые min(a1, a2, N)
        contested = min(a1, a2, N)
        remaining_neutral = N - contested

        r1_unique = a1 - contested
        r2_unique = a2 - contested

        # Выдать оставшийся нейтрал по очереди (справедливо)
        give1 = min(r1_unique, remaining_neutral)
        remaining_neutral -= give1
        give2 = min(r2_unique, remaining_neutral)
        remaining_neutral -= give2

        # Обновляем состояние игроков
        self.p1.territory += give1
        self.p1.expanded_total += give1
        self.p2.territory += give2
        self.p2.expanded_total += give2

        # Итоговое количество нейтрала
        self.neutral_territory = remaining_neutral + contested

        self.trace(
            f"Expands: P1 want={a1} P2 want={a2} | contested={contested} "
            f"granted P1={give1} P2={give2} | neutral={self.neutral_territory}"
        )

        # очистить заявки на следующий ход
        self.p1.pending_expands = 0
        self.p2.pending_expands = 0

    # ---------- бой ----------
    def _resolve_combat(self):
        dmg12 = max(0, self.p1.attack - self.p2.defense)
        dmg21 = max(0, self.p2.attack - self.p1.defense)

        loss1 = min(dmg21, self.p1.territory)
        loss2 = min(dmg12, self.p2.territory)

        self.p1.territory -= loss1
        self.p2.territory -= loss2
        self.neutral_territory += loss1 + loss2

        self.trace(
            f"Combat: P1 dmg={dmg12} P2 dmg={dmg21} | terr P1={self.p1.territory} "
            f"P2={self.p2.territory} neutral={self.neutral_territory}"
        )

    # ---------- победитель ----------
    def _winner_declared(self) -> bool:
        return self._check_winner() is not None

    def _check_winner(self, is_end=False) -> str | None:
        if self.p1.territory == 0 and self.p2.territory == 0:
            return "draw"
        if self.p1.territory == 0:
            return "player2"
        if self.p2.territory == 0:
            return "player1"
        if is_end:
            g1 = self.p1.gold 
            g2 = self.p2.gold
            if g1 == g2:
                return "draw"
            elif g1 > g2:
                return "player1"
            return "player2"
        return None

    # ---------- результат ----------
    def _result(self, is_end=False) -> Dict[str, Any]:
        return {
            "winner": self._check_winner(is_end=is_end),
            "turns": self.turn,
            "neutral": self.neutral_territory,
            "p1": {
                "territory": self.p1.territory,
                "gold": self.p1.gold,
                "attack": self.p1.attack,
                "defense": self.p1.defense,
            },
            "p2": {
                "territory": self.p2.territory,
                "gold": self.p2.gold,
                "attack": self.p2.attack,
                "defense": self.p2.defense,
            },
        }
