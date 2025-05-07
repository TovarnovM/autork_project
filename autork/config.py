from pydantic_settings import BaseSettings

class GameSettings(BaseSettings):
    MAX_TURNS: int = 200
    START_GOLD: int = 50
    START_TERRITORY: int = 30
    NEUTRAL_TERRITORY: int = 40
    START_ATTACK: int = 0
    START_DEFENSE: int = 0

    GOLD_PER_LAND: int = 1
    # цены
    EXPAND_BASE: int = 10
    EXPAND_STEP: int = 1
    ATK_BASE: int = 20
    ATK_K: int = 1
    DEF_BASE: int =  9
    DEF_K: int = 3
    # содержание
    MAINT_ATK: int = 4
    MAINT_DEF: int = 1
    # разведка
    SCOUT_COST: int = 20

settings = GameSettings()      # доступен из других модулей
