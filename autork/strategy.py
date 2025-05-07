from abc import ABC, abstractmethod
from typing import Dict, Any
import random

# ---------- интерфейсы ----------
class Strategy(ABC):
    sname = 'base empty'
    author = 'system'
    """Базовый интерфейс стратегии-бота."""
    @abstractmethod
    def reset(self, initial_observation: Dict[str, Any]) -> None: ...
    
    @abstractmethod
    def step(self, observation: Dict[str, Any]) -> Dict[str, Any]: ...

# ---------- 2 простых примера ----------
class RandomStrategy(Strategy):
    sname = 'random'
    

    def reset(self, observation): 
        pass

    def step(self, obs):
        prices = obs["prices"]
        gold = obs["limits"]["gold"]
        whatdo, price_key = random.choice([
            ('expand', 'expand_next'), ('spend_attack', 'buy_attack'), ('spend_defense', 'buy_defense')])
        
        res = {"expand": 0, "spend_attack": 0, "spend_defense": 0, "scout": False}
        if gold >= prices[price_key]:
            res[whatdo] = prices[price_key]
        else:
            whatdo = random.choice(['sell_attack', 'sell_defense'])
            res[whatdo] = 1
        return res

class GreedyExpansionStrategy(Strategy):
    sname = 'greedy_expansion' # имя стратегии
    
    def reset(self, observation): pass
    def step(self, obs):
        # тратим всё золото на расширение, если есть нейтрал
        gold = obs["my"]["gold"]
        neutral = obs["neutral_territory"]
        plan = min(neutral, gold // obs["prices"]["expand_next"])
        return {"expand": plan, "spend_attack": 0,
                "spend_defense": 0, "scout": False}
