"""autork.gui – Pygame‑визуализация по ходам
-------------------------------------------------
Запускать как подмодуль пакета:
    python ‑m autork.gui
или из корня проекта:
    python -m autork
(см. __main__.py).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import pygame

from autork.engine import Engine  
from autork.strategy import RandomStrategy  # примеры
from autork.config import settings as _settings


# --------------------------------------------------
class GuiEngine(Engine):
    """Движок + простая визуализация. После каждого хода перерисовывает окно."""

    # размеры окна и элементов
    WIDTH, HEIGHT = 960, 600
    PANEL_W = 220      # инфо‑панель игрока
    BAR_H = 44         # высота нижней трёхцветной полосы‑карты
    MARGIN = 12

    # --- цвета (RGB) ---
    BLUE = (60, 120, 255)
    RED = (255, 85, 85)
    GREY = (160, 160, 160)
    WHITE = (240, 240, 240)
    BACKGROUND = (25, 25, 25)
    GREEN = (70, 200, 70)
    DOWN_RED = (220, 60, 60)

    FONT_MAIN = "DejaVu Sans"  # содержит стрелки ↑ ↓ →

    def __init__(self, strat1, strat2, cfg=None, fps=7):
        if cfg is None:
            cfg = _settings
        super().__init__(strat1, strat2, trace=print, game_settings=cfg)
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Игра – ход 0")
        # шрифты
        self.font = pygame.font.SysFont(self.FONT_MAIN, 20)
        self.font_small = pygame.font.SysFont(self.FONT_MAIN, 16)
        self.font_big = pygame.font.SysFont(self.FONT_MAIN, 26, bold=True)
        # для подсчёта изменения золота
        self._prev_gold: Tuple[int, int] = (self.p1.gold, self.p2.gold)
        self.clock = pygame.time.Clock()
        self.fps = fps

    # -------------------------------------------------- GUI helpers
    def _draw_text(self, txt, pos, color=WHITE, center=False, font=None):
        if font is None:
            font = self.font
        surf = font.render(txt, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        self.screen.blit(surf, rect)
        return rect

    def _draw_player_panel(self, pl, x, y, delta_gold, is_left: bool):
        panel_rect = pygame.Rect(x, y, self.PANEL_W, self.HEIGHT - self.BAR_H - 2 * self.MARGIN)
        pygame.draw.rect(self.screen, (40, 40, 40), panel_rect)
        pygame.draw.rect(self.screen, self.WHITE, panel_rect, 1)

        pad = 8
        line_y = y + pad
        align = "left" if is_left else "right"
        def line(text, color=self.WHITE, font=None):
            nonlocal line_y
            if align == "left":
                pos = (x + pad, line_y)
            else:
                pos = (x + pad, line_y)
            self._draw_text(text, pos, color, center=False, font=font)
            line_y += 26

        arrow = "↑" if delta_gold > 0 else ("↓" if delta_gold < 0 else "→")
        arrow_color = self.GREEN if delta_gold > 0 else (self.DOWN_RED if delta_gold < 0 else self.WHITE)

        head = f"Игрок {'1' if is_left else '2'}"
        line(head, font=self.font_big)
        line(f"Территория: {pl.territory}")
        line(f"Атака: {pl.attack}")
        line(f"Защита: {pl.defense}")
        # золото + дельта
        gold_txt = f"Золото: {pl.gold} {arrow}{abs(delta_gold)}"
        line(gold_txt, arrow_color)

    def _draw_relation_bar(self, numerator: int, denominator: int, caption: str, top_y: int) -> int:
        """Толстая цветная полоса‑отношение с иконками.

        * Слева/справа отображаются соответствующие иконки (меч/щит).
        * Полоса закрашивается **синим** слева до разделителя и **красным** справа.
        * Разделитель определяется отношением (num/denom) ограниченным [0;2].
        * Возвращает y‑координату для следующего блока.
        """
        # ---------------- загружаем иконки лениво ----------------
        bar_h = 30  # толщина полосы
        icon_pad = 6  # отступ между иконкой и полосой
        if not hasattr(self, "_rel_icons"):
            here = Path(__file__).parent

            def _load(name: str):
                path = here / name
                if path.exists():
                    try:
                        return pygame.image.load(str(path)).convert_alpha()
                    except Exception:
                        pass
                # Заглушка, если файла нет – рисуем пустой квадрат
                surf = pygame.Surface((32, 32), pygame.SRCALPHA)
                pygame.draw.rect(surf, self.GREY, (0, 0, 32, 32), 2)
                return surf

            raw = {
                "blue_sword": _load("blue_sword.png"),
                "red_sword": _load("red_sword.png"),
                "blue_shield": _load("blue_shield.png"),
                "red_shield": _load("red_shield.png"),
            }
            # Масштабируем до высоты полосы
            self._rel_icons = {k: pygame.transform.smoothscale(img, (bar_h, bar_h)) for k, img in raw.items()}

        icons = self._rel_icons
        # ---------------- определяем иконки для данного caption ----------------
        if "Atk₁" in caption:
            left_icon = icons["blue_sword"]
            right_icon = icons["red_shield"]
        else:  # "Def₁" в первой части
            left_icon = icons["blue_shield"]
            right_icon = icons["red_sword"]

        # ---------------- геометрия ----------------
        icon_w = left_icon.get_width()
        left_panel_end = self.MARGIN + self.PANEL_W
        right_panel_start = self.WIDTH - self.MARGIN - self.PANEL_W

        x_icon_left = left_panel_end + self.MARGIN
        x_icon_right = right_panel_start - self.MARGIN - icon_w

        bar_x = x_icon_left + icon_w + icon_pad
        bar_w = x_icon_right - icon_pad - bar_x

        # фон (серый рамкой, затем рисуем цветные сегменты)
        pygame.draw.rect(self.screen, self.GREY, (bar_x, top_y, bar_w, bar_h))

        # считаем позицию разделителя
        if denominator == 0:
            ratio = 2.0  # бесконечность → край
        else:
            ratio = numerator / denominator
        ratio = max(0.0, min(2.0, ratio))  # clamp 0..2
        pos_x = bar_x + (ratio / 2.0) * bar_w
        # цветные сегменты
        pygame.draw.rect(self.screen, self.BLUE, (bar_x, top_y, int(pos_x - bar_x), bar_h))
        pygame.draw.rect(self.screen, self.RED, (int(pos_x), top_y, int(bar_x + bar_w - pos_x), bar_h))
        # рамка
        pygame.draw.rect(self.screen, self.WHITE, (bar_x, top_y, bar_w, bar_h), 1)

        # иконки
        self.screen.blit(left_icon, (x_icon_left, top_y))
        self.screen.blit(right_icon, (x_icon_right, top_y))

        # подпись сверху (по центру полосы)
        caption_text = f"{caption}: {numerator}/{denominator if denominator else '∞'}"
        self._draw_text(caption_text, (bar_x + bar_w // 2, top_y - 24), center=True)

        return top_y + bar_h + 40  # смещение для следующего блока

    def _draw_territory_bar(self):
        y = self.HEIGHT - self.BAR_H - self.MARGIN
        x = self.MARGIN
        w = self.WIDTH - 2 * self.MARGIN
        total = self.p1.territory + self.p2.territory + self.neutral_territory
        if total == 0:
            total = 1
        # сегменты
        w1 = int(w * self.p1.territory / total)
        w_neu = int(w * self.neutral_territory / total)
        w2 = w - w1 - w_neu
        # прямоугольники
        pygame.draw.rect(self.screen, self.BLUE, (x, y, w1, self.BAR_H))
        pygame.draw.rect(self.screen, self.GREY, (x + w1, y, w_neu, self.BAR_H))
        pygame.draw.rect(self.screen, self.RED, (x + w1 + w_neu, y, w2, self.BAR_H))
        # граница
        pygame.draw.rect(self.screen, self.WHITE, (x, y, w, self.BAR_H), 1)
        # подписи
        cx1 = x + w1 // 2
        cx_neu = x + w1 + w_neu // 2
        cx2 = x + w1 + w_neu + w2 // 2
        if w1 > 40:
            self._draw_text(str(self.p1.territory), (cx1, y + self.BAR_H // 2), center=True)
        if w_neu > 40:
            self._draw_text(str(self.neutral_territory), (cx_neu, y + self.BAR_H // 2), center=True)
        if w2 > 40:
            self._draw_text(str(self.p2.territory), (cx2, y + self.BAR_H // 2), center=True)

    # -------------------------------------------------- главная функция отрисовки
    def _render(self):
        """Полная перерисовка кадра после хода."""
        # расчёт дельты золота для стрелочек
        delta1 = self.p1.gold - self._prev_gold[0]
        delta2 = self.p2.gold - self._prev_gold[1]
        self._prev_gold = (self.p1.gold, self.p2.gold)

        # заголовок окна
        pygame.display.set_caption(f"Игра – ход {self.turn}")
        self.screen.fill(self.BACKGROUND)

        # панели игроков (слева / справа)
        self._draw_player_panel(self.p1, self.MARGIN, self.MARGIN, delta1, is_left=True)
        self._draw_player_panel(self.p2, self.WIDTH - self.PANEL_W - self.MARGIN, self.MARGIN, delta2, is_left=False)

        # центральные шкалы‑отношения
        next_y = self.MARGIN + 24  # небольшое смещение от верха
        next_y = self._draw_relation_bar(self.p1.attack, self.p2.defense, "Atk₁ / Def₂", next_y)
        next_y = self._draw_relation_bar(self.p1.defense, self.p2.attack, "Def₁ / Atk₂", next_y)

        # нижняя карта‑полоса
        self._draw_territory_bar()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def _handle_gui_events(self):
        running = True
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
        return running

    # -------------------------------------------------- переопределяем run()
    # def run(self):  # type: ignore[override]
    #     # инициализация стратегий
    #     self.reset()
    #     self.s1.reset(self._observation(1))
    #     self.s2.reset(self._observation(2))
        
    #     self._render()

    #     running = True
        
    #     while running and self.turn < self.cfg.MAX_TURNS:
    #         # обработка событий окна
    #         for event in pygame.event.get():
    #             if event.type == pygame.QUIT:
    #                 running = False
    #                 break
    #         if not running:
    #             break

    #         # следующий ход
    #         self.turn += 1
    #         self._play_turn()
    #         # дельта золота
            
    #         # отрисовать
    #         self._render()
    #         # победа?
    #         if self._winner_declared():
    #             break
    #         clock.tick(5)  # ~5 fps

    #     # показываем финальную позицию ещё 3 сек.
        
    #     return self._result(is_end=True)

    def _final_render(self):
        pygame.time.wait(3000)
        pygame.quit()

# -------------------------------------------------- точка входа: python -m autork.gui

def main():  # noqa: D401 – one‑liner description
    p1 = RandomStrategy()
    p2 = RandomStrategy()
    game = GuiEngine(p1, p2)
    game.run()


if __name__ == "__main__":
    # Если файл запущен как скрипт («python -m autork.gui»), запускаем демо‑игру
    main()
