import pygame

from games.wheelchair.game import wheelchair_game, wheelchair_game_over, wheelchair_input_username
from shared.constants import TEXT_COLOR, TEXT_FONT, TITLE_FONT
from shared.leaderboard import run_leaderboard
from shared.state import Game, Scene, state
from shared.ui import Button, Grid, fill_surface, init_pygame, mouse_pos_to_surface, scale_to_screen


def wheelchair_launcher(surface: pygame.Surface, screen: pygame.Surface) -> None:
    buttons = [
        Button(Grid.pos(6, 6), "PLAY", TEXT_FONT, on_click=lambda: state.go_to(Scene.WHEELCHAIR_INPUT_USERNAME)),
        Button(Grid.pos(6, 11), "QUIT", TEXT_FONT, on_click=lambda: state.go_to(Scene.QUIT)),
    ]

    while state.scene == Scene.LAUNCHER:
        mouse_pos = mouse_pos_to_surface(screen)

        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN:
                    for btn in buttons:
                        btn.handle_click(mouse_pos)

        fill_surface(surface)

        title = TITLE_FONT.render("WHEELCHAIR", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        for btn in buttons:
            btn.update(surface, mouse_pos)

        scale_to_screen(surface, screen)


def run_wheelchair(surface: pygame.Surface, screen: pygame.Surface) -> None:
    while state.scene != Scene.QUIT:
        match state.scene:
            case Scene.LAUNCHER:
                wheelchair_launcher(surface, screen)
            case Scene.WHEELCHAIR_INPUT_USERNAME:
                wheelchair_input_username(surface, screen)
            case Scene.WHEELCHAIR_GAME:
                wheelchair_game(surface, screen)
            case Scene.WHEELCHAIR_GAME_OVER:
                wheelchair_game_over(surface, screen)
            case Scene.LEADERBOARD:
                run_leaderboard(surface, screen)
            case Scene.QUIT:
                break


if __name__ == "__main__":
    surface, screen = init_pygame()
    state.game = Game.WHEELCHAIR
    run_wheelchair(surface, screen)
    pygame.quit()
