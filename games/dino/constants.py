from games.dino.assets import BackgroundAsset, BirdAsset, CactusAsset, DinoAsset

# game assets
DINO_GAME_ASSETS = [DinoAsset, CactusAsset, BirdAsset, BackgroundAsset]

ANIM_SPEED = 5

# Zone marker constants (ground strip rendered beneath each obstacle)
ZONE_HEIGHT = 18  # pixel height of the strip
ZONE_COLOR = (255, 255, 255, 110)  # white, semi-transparent - marks the safe press window only
