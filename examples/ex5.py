from __future__ import annotations
"""demo_strategies.py – пример использования и сравнительный запуск стратегий

Запускает мини‑турнир «каждый с каждым» между четырьмя реализациями Strategy
из файла *bot.py* и выводит итоговую таблицу побед/поражений.

Запуск:
    python demo_strategies.py

Требует, чтобы рядом находились `bot.py` и `engine.py` (или чтобы они были
установлены как модуль `autork`).
"""

import sys

# путь до autork
# print(sys.path)
sys.path.append('.')

import itertools
from collections import Counter
from dataclasses import dataclass
from typing import Type

from autork.engine import Engine  # игровой движок
from autork.strategies_demo import (  # наши стратегии
    UltraAggressiveStrategy,
    UltraDefensiveStrategy,
    EconomicBoomStrategy,
    AdaptiveOpponentStrategy,
    AdaptiveOpponentStrategyV2,
    UltraDefensiveStrategyV2,  # добавлено новое определение UltraDefensiveStrategyV2
    EconomicBoomStrategyV2
)

# ---------------------------------------------------------------------------
@dataclass
class StratEntry:
    name: str
    cls: Type
    kwargs: dict[str, object] | None = None

    def make(self):
        return self.cls(**(self.kwargs or {}))


STRATEGIES: list[StratEntry] = [
    StratEntry("Aggro", UltraAggressiveStrategy),
    StratEntry("Turtle", UltraDefensiveStrategy),
    StratEntry("EcoBoom", EconomicBoomStrategy),
    StratEntry("Adaptive", AdaptiveOpponentStrategy),
    StratEntry("Adaptive2", AdaptiveOpponentStrategyV2),
    StratEntry("TurtleV2", UltraDefensiveStrategyV2),  
    StratEntry("EcoBoomV2", EconomicBoomStrategyV2)  
]

# ---------------------------------------------------------------------------

def play_match(a: StratEntry, b: StratEntry) -> int:
    """Возвращает 1, если выиграл A, -1 если выиграл B, 0 – ничья."""
    s1 = a.make()
    s2 = b.make()
    game = Engine(s1, s2, trace=None)  # без логов
    result = game.run()
    winner = result["winner"]  # 0 – ничья, 1 – левый, 2 – правый
    if winner == 'player1':
        return 1
    if winner == 'player2':
        return -1
    return 0


def main() -> None:
    score = Counter()

    for a, b in itertools.permutations(STRATEGIES, 2):
        outcome = play_match(a, b)
        if outcome == 1:
            score[a.name] += 3
        elif outcome == -1:
            score[b.name] += 3
        else:
            score[a.name] += 1
            score[b.name] += 1

    # --- печать таблицы ---
    print("=== RESULTS ===")
    width = max(len(s.name) for s in STRATEGIES) + 2
    for s in STRATEGIES:
        print(f"{s.name:<{width}} : {score[s.name]}")


if __name__ == "__main__":
    main()
