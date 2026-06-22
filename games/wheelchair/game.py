import pygame

from shared.constants import FPS, HEADING_FONT, SUBTEXT_FONT, TEXT_COLOR, TEXT_FONT, TITLE_FONT
from shared.leaderboard import Leaderboard
from shared.state import Scene, state
from shared.ui import Button, Grid, TextInput, fill_surface, mouse_pos_to_surface, scale_to_screen


def wheelchair_input_username(surface: pygame.Surface, screen: pygame.Surface) -> None:
    def play_wheelchair() -> None:
        state.username_one = text_input.get_text()
        state.go_to(Scene.WHEELCHAIR_GAME)

    text_input = TextInput(Grid.pos(6, 4), TEXT_FONT, "PLAYER 1")

    play_button = Button(Grid.pos(6, 6), "PLAY", TEXT_FONT, on_click=play_wheelchair)

    buttons = [
        play_button,
        Button(Grid.pos(2, 11), "BACK", TEXT_FONT, on_click=state.go_back),
        Button(Grid.pos(6, 11), "LEADERBOARD", TEXT_FONT, on_click=lambda: state.go_to(Scene.LEADERBOARD)),
        Button(Grid.pos(10, 11), "QUIT", TEXT_FONT, on_click=lambda: state.go_to(Scene.QUIT)),
    ]

    while state.scene == Scene.WHEELCHAIR_INPUT_USERNAME:
        mouse_pos = mouse_pos_to_surface(screen)

        play_button.disabled = not text_input.get_text()

        for event in pygame.event.get():
            text_input.handle_event(event)

            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN:
                    text_input.handle_click(mouse_pos)
                    for btn in buttons:
                        btn.handle_click(mouse_pos)

        fill_surface(surface)

        title = TITLE_FONT.render("WHEELCHAIR", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        text_input.update(surface, mouse_pos)
        for btn in buttons:
            btn.update(surface, mouse_pos)

        scale_to_screen(surface, screen)


def wheelchair_game(surface: pygame.Surface, screen: pygame.Surface) -> None:
    def handle_restart() -> None:
        nonlocal game_started
        game_started = False
        state.score_one = 0

    buttons = [
        Button(Grid.pos(2, 11), "RESTART", TEXT_FONT, on_click=handle_restart),
        Button(
            Grid.pos(6, 11), "NEW GAME", TEXT_FONT, on_click=lambda: state.reset_to(Scene.WHEELCHAIR_INPUT_USERNAME)
        ),
        Button(Grid.pos(10, 11), "QUIT", TEXT_FONT, on_click=lambda: state.go_to(Scene.QUIT)),
    ]

    clock = pygame.time.Clock()
    game_started = False
    paused = False

    while state.scene == Scene.WHEELCHAIR_GAME:
        clock.tick(FPS)
        mouse_pos = mouse_pos_to_surface(screen)

        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game_started = True
                        paused = False
                    if event.key == pygame.K_ESCAPE:
                        paused = not paused
                case pygame.MOUSEBUTTONDOWN:
                    for btn in buttons:
                        btn.handle_click(mouse_pos)

        fill_surface(surface)

        # status text
        if not game_started:
            status = TEXT_FONT.render("Press ENTER to start", True, TEXT_COLOR)
            surface.blit(status, status.get_rect(center=Grid.pos(6, 4)))
        elif paused:
            paused_txt = TEXT_FONT.render("Paused (ESC to resume)", True, TEXT_COLOR)
            surface.blit(paused_txt, paused_txt.get_rect(center=Grid.pos(6, 4)))
            for btn in buttons:
                btn.update(surface, mouse_pos)
        else:
            temp = TITLE_FONT.render("WHEELCHAIR", True, TEXT_COLOR)
            surface.blit(temp, temp.get_rect(center=Grid.pos(6, 6)))

        scale_to_screen(surface, screen)


def wheelchair_game_over(surface: pygame.Surface, screen: pygame.Surface) -> None:
    score = state.score_one
    Leaderboard.record_wheelchair(state.username_one, score)

    buttons = [
        Button(Grid.pos(3, 5), "PLAY AGAIN", TEXT_FONT, on_click=lambda: state.reset_to(Scene.WHEELCHAIR_GAME)),
        Button(Grid.pos(9, 5), "NEW GAME", TEXT_FONT, on_click=lambda: state.reset_to(Scene.WHEELCHAIR_INPUT_USERNAME)),
        Button(Grid.pos(6, 7), "LEADERBOARD", TEXT_FONT, on_click=lambda: state.go_to(Scene.LEADERBOARD)),
        Button(Grid.pos(6, 9), "MAIN MENU", TEXT_FONT, on_click=lambda: state.reset_to(Scene.LAUNCHER)),
        Button(Grid.pos(6, 11), "QUIT", TEXT_FONT, on_click=lambda: state.go_to(Scene.QUIT)),
    ]

    while state.scene == Scene.WHEELCHAIR_GAME_OVER:
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

        heading = HEADING_FONT.render("GAME OVER", True, TEXT_COLOR)
        surface.blit(heading, heading.get_rect(center=Grid.pos(6, 2)))

        score_text = SUBTEXT_FONT.render(f"{state.username_one or 'PLAYER'} - Score {score}", True, TEXT_COLOR)
        surface.blit(score_text, score_text.get_rect(center=Grid.pos(6, 3)))

        for btn in buttons:
            btn.update(surface, mouse_pos)

        scale_to_screen(surface, screen)
