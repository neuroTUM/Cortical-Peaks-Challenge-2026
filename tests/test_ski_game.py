import sys

import pygame

from games.ski.state import create_initial_state
from games.ski.update import update_game_state
from games.ski.viewer import SkiViewerRenderer
from shared.ui import init_pygame


def run_local_test() -> None:
    print("Which game mode do you want to test?")  # noqa: T201
    print("1. Static Obstacles (SK1)")
    print("2. Dynamic Obstacles (SK2)")
    choice = input("Enter 1 or 2 (default 1): ").strip()
    is_dynamic = choice == "2"

    mode_name = "Dynamic" if is_dynamic else "Static"
    surface, screen = init_pygame(f"SKI Game - Local Test ({mode_name})")

    clock = pygame.time.Clock()

    renderer = SkiViewerRenderer()

    state = create_initial_state(username="Tester_Keys", dynamic=is_dynamic)
    state.is_paused = False
    state.countdown = 0.0

    print("--- Local Test Harness Started ---")
    print(f"Mode: {mode_name}")
    print("Press UP/DOWN to move forward/backward")
    print("Press LEFT/RIGHT to rotate")
    print("Press ESCAPE to quit")

    while not state.game_over:
        clock.tick(30)
        player_input = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player_input = "rotate_left"
        elif keys[pygame.K_RIGHT]:
            player_input = "rotate_right"
        elif keys[pygame.K_UP]:
            player_input = "forward"
        elif keys[pygame.K_DOWN]:
            player_input = "backward"

        state = update_game_state(state, player_input)

        renderer.render_frame(surface, screen, state)

        pygame.display.flip()

    print("Game Over!")
    pygame.quit()


if __name__ == "__main__":
    run_local_test()
