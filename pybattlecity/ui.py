import pygame
from config import ATLAS, GAME_WIDTH, GAME_HEIGHT
from util import GameObject


class GameOverLabel(GameObject):
    def __init__(self):
        super().__init__()
        self._image = ATLAS().image_at(36, 23, 4, 2)
        size = ATLAS().real_sprite_size
        self.size = (size * 4, size * 2)

    def place_at_center(self, go: GameObject):
        x, y = go.position
        w, h = go.size
        self.position = x + (w - self.size[0]) // 2, y + (h - self.size[1]) // 2 + 2

    def render(self, screen):
        screen.blit(self._image, self.position)


class GameWinLabel(GameObject):
    def __init__(self):
        super().__init__()
        # Dùng sprite khác hoặc chữ WIN
        font = pygame.font.SysFont("Arial", 40, True)
        self._image = font.render("YOU WIN!", True, (255, 255, 0))
        self.size = self._image.get_size()
        self.position = (GAME_WIDTH // 2 - self.size[0] // 2,
                         GAME_HEIGHT // 2 - self.size[1] // 2)

    def render(self, screen):
        screen.blit(self._image, self.position)


class TankStatsUI(GameObject):
    def __init__(self, tank):
        super().__init__()
        self.tank = tank
        self.font = pygame.font.SysFont("Arial", 20)

    def render(self, screen):
        gun_level = self.tank.tank_type.name
        shield = "ON" if self.tank.shielded else "OFF"

        txt = f"GUN: {gun_level} | Shield: {shield}"
        img = self.font.render(txt, True, (255, 255, 255))
        screen.blit(img, (10, GAME_HEIGHT - 30))
