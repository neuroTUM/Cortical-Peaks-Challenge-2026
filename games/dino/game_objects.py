import random

import pygame

from games.dino.assets import BackgroundAsset
from games.dino.config import dino_config
from shared.asset_manager import AssetManager
from shared.constants import WIDTH
from shared.ui import Grid, scale_to_fit


class CloudLayer:
    _pattern_width = WIDTH * 2
    _num_clouds = 8

    def __init__(self) -> None:
        cloud_w = Grid.x(dino_config.cloud_width)
        cloud_h = Grid.y(dino_config.cloud_height)
        cloud_sprite = scale_to_fit(AssetManager.get(BackgroundAsset.CLOUD), cloud_w, cloud_h)

        self.img = pygame.Surface((self._pattern_width, Grid.y(8)), pygame.SRCALPHA)

        for _ in range(self._num_clouds):
            x = random.randint(0, self._pattern_width - cloud_w)
            y = Grid.y(random.randint(dino_config.cloud_y_min, dino_config.cloud_y_max)) - Grid.y(
                dino_config.cloud_y_min
            )
            self.img.blit(cloud_sprite, (x, y))

        self.width = self.img.get_width()
        self.y = Grid.y(dino_config.cloud_y_min)

    def draw(self, surface: pygame.Surface, offset: int) -> None:
        tile_offset = offset % self.width
        x = -tile_offset

        while x < WIDTH:
            surface.blit(self.img, (x, self.y))
            x += self.width


class Track:
    def __init__(self) -> None:
        self.img = AssetManager.get(BackgroundAsset.TRACK)
        self.width = self.img.get_width()
        self.y = Grid.y(10) - dino_config.track_y_offset

    def draw(self, surface: pygame.Surface, offset: int) -> None:
        tile_offset = offset % self.width
        x = -tile_offset

        while x < WIDTH:
            surface.blit(self.img, (x, self.y))
            x += self.width
