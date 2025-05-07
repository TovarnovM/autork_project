import sys

# путь до autork
# print(sys.path)
sys.path.append('.')

from autork.gui import GuiEngine
from autork.strategy import RandomStrategy, GreedyExpansionStrategy

s1 = RandomStrategy()
s2 = GreedyExpansionStrategy()

eng = GuiEngine(s1, s2)
res = eng.run()
print(res)

