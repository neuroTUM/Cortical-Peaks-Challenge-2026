from enum import Enum
from typing import TYPE_CHECKING, ClassVar

import pygame

from shared.constants import ASSETS_DIR
from shared.log import log
from shared.ui import Grid

if TYPE_CHECKING:
    from pathlib import Path


class Asset(Enum):
    @property
    def asset_dir(self) -> Path:
        return ASSETS_DIR

    @property
    def path(self) -> Path:
        return self.asset_dir / str(self.value)


class AssetManager:
    _assets: ClassVar[dict[Asset, pygame.Surface]] = {}

    @classmethod
    def _load(cls, asset: Asset) -> None:
        if asset in cls._assets:
            return

        try:
            cls._assets[asset] = pygame.image.load(asset.path).convert_alpha()
        except FileNotFoundError, pygame.error:
            log.exception("Error loading asset %s", asset.path)
            # fallback surface
            cls._assets[asset] = pygame.Surface((Grid.x(1), Grid.y(1)))
            cls._assets[asset].fill("red")

    @classmethod
    def load_all(cls, *assets: type[Asset]) -> None:
        for asset in assets:
            for element in asset:
                cls._load(element)

    @classmethod
    def get(cls, asset: Asset) -> pygame.Surface:
        if asset not in cls._assets:
            cls._load(asset)
        return cls._assets[asset]
