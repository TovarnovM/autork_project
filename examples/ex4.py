import sys

# путь до autork
# print(sys.path)
sys.path.append('.')

from autork.gui import GuiEngine
from autork.strategies_demo import EconomicBoomStrategy, UltraAggressiveStrategy, UltraDefensiveStrategy

s1 = UltraDefensiveStrategy()
s2 = UltraAggressiveStrategy()

eng = GuiEngine(s1, s2)
res = eng.run()
print(res)

