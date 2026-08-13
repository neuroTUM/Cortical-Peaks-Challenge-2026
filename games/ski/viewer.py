from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from games.ski.assets import ObstacleAsset, SkiAsset
from games.ski.config import ski_config
from shared.asset_manager import AssetManager
from shared.constants import ACCENT_COLOR, BACKGROUND_COLOR, DISABLED_COLOR, SUBTEXT_FONT, TEXT_COLOR
from shared.ui import Grid, scale_to_fit, scale_to_screen

if TYPE_CHECKING:
    from collections.abc import Callable

    from games.ski.state import SkiState


def _roadmap_progress(state: SkiState) -> float:
    track_distance = max(1.0, state.start_y - state.goal_y)
    travelled = state.start_y - state.y
    return max(0.0, min(1.0, travelled / track_distance))


class SkiViewerRenderer:
    def __init__(self) -> None:
        AssetManager.load_all(SkiAsset, ObstacleAsset)

        size = ski_config.player_bounding_radius * 2
        raw_brain_moving = AssetManager.get(SkiAsset.BRAIN_MOVING)
        self.brain_moving_img = scale_to_fit(raw_brain_moving, size, size)

        raw_brain_stopped = AssetManager.get(SkiAsset.BRAIN_STOPPED)
        self.brain_stopped_img = scale_to_fit(raw_brain_stopped, size, size)

        # Load and scale obstacle sprites
        obs_size = ski_config.obstacle_radius * 2

        raw_obs = AssetManager.get(ObstacleAsset.SPRITE)
        self.obs_img = scale_to_fit(raw_obs, obs_size, obs_size)

        raw_moving_obs = AssetManager.get(ObstacleAsset.MOVING_SPRITE)
        self.moving_obs_img = scale_to_fit(raw_moving_obs, obs_size, obs_size)

        self.arrow_img = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.polygon(self.arrow_img, ACCENT_COLOR, [(0, 30), (15, 0), (30, 30), (15, 20)])

    def _draw_roadmap(self, surface: pygame.Surface, state: SkiState) -> None:
        progress = _roadmap_progress(state)

        track_width = 8
        track_x = Grid.x(0.18)
        track_top = Grid.y(2.5)
        track_bottom = Grid.y(8.5)
        track_height = track_bottom - track_top

        track_rect = pygame.Rect(track_x - track_width // 2, track_top, track_width, track_height)

        track_color = DISABLED_COLOR
        progress_color = ACCENT_COLOR

        pygame.draw.rect(surface, track_color, track_rect, border_radius=track_width // 2)

        fill_height = int(track_rect.height * progress)
        if fill_height > 0:
            fill_rect = pygame.Rect(track_rect.left, track_rect.bottom - fill_height, track_rect.width, fill_height)
            pygame.draw.rect(surface, progress_color, fill_rect, border_radius=track_width // 2)

        start_center = (track_rect.centerx, track_rect.bottom)
        goal_center = (track_rect.centerx, track_rect.top)
        current_center = (track_rect.centerx, track_rect.bottom - fill_height)

        pygame.draw.circle(surface, track_color, start_center, 8)
        pygame.draw.circle(surface, BACKGROUND_COLOR, start_center, 4)

        pygame.draw.circle(surface, progress_color, goal_center, 8)
        pygame.draw.circle(surface, BACKGROUND_COLOR, goal_center, 4)

        pygame.draw.circle(surface, progress_color, current_center, 7)
        pygame.draw.circle(surface, track_color, current_center, 7, width=2)

    def render_frame(
        self,
        surface: pygame.Surface,
        screen: pygame.Surface,
        state: SkiState,
        overlay: Callable[[pygame.Surface], None] | None = None,
    ) -> None:
        surface.fill(BACKGROUND_COLOR)

        cam_x = state.start_x - Grid.x(6)
        cam_y = state.y - Grid.y(8)

        goal_draw_x = state.goal_x - cam_x
        goal_draw_y = state.goal_y - cam_y

        player_draw_x = state.x - cam_x
        player_draw_y = state.y - cam_y

        screen_w = Grid.x(12)
        margin = ski_config.track_margin_px
        b_vis_rad = ski_config.barrier_radius
        b_pad = ski_config.barrier_transparent_padding

        left_wall_world = margin + b_vis_rad + (b_vis_rad - b_pad)
        right_wall_world = screen_w - margin - b_vis_rad - (b_vis_rad - b_pad)
        top_wall_world = state.goal_y - ski_config.track_top_margin + (b_vis_rad - b_pad)
        bottom_wall_world = state.start_y + ski_config.track_bottom_margin - (b_vis_rad - b_pad)

        draw_left = int(left_wall_world - cam_x)
        draw_right = int(right_wall_world - cam_x)
        draw_top = int(top_wall_world - cam_y)
        draw_bottom = int(bottom_wall_world - cam_y)

        cyan_color = (0, 255, 255)
        line_thickness = 6

        rect_width = draw_right - draw_left
        rect_height = draw_bottom - draw_top
        boundary_rect = pygame.Rect(draw_left, draw_top, rect_width, rect_height)

        pygame.draw.rect(surface, cyan_color, boundary_rect, width=line_thickness)

        pygame.draw.circle(
            surface,
            ACCENT_COLOR,
            (int(goal_draw_x), int(goal_draw_y)),
            ski_config.goal_radius,
            width=3,
        )

        goal_txt = SUBTEXT_FONT.render("GOAL", True, ACCENT_COLOR)
        surface.blit(goal_txt, goal_txt.get_rect(center=(goal_draw_x, goal_draw_y + ski_config.goal_radius + 16)))

        for obs in state.obstacles:
            draw_x = obs.x - cam_x
            draw_y = obs.y - cam_y

            img_to_draw = self.moving_obs_img if obs.speed > 0 else self.obs_img

            rect = img_to_draw.get_rect(center=(draw_x, draw_y))
            surface.blit(img_to_draw, rect.topleft)

        if goal_draw_y < 0:
            dx = state.goal_x - state.x
            dy = state.goal_y - state.y

            angle = math.degrees(math.atan2(-dy, dx))
            rotation = angle - 90
            rotated_arrow = pygame.transform.rotate(self.arrow_img, rotation)

            arrow_x = player_draw_x
            arrow_y = player_draw_y - ski_config.player_bounding_radius - 40

            arrow_rect = rotated_arrow.get_rect(center=(arrow_x, arrow_y))
            surface.blit(rotated_arrow, arrow_rect.topleft)

        draw_x = state.x - cam_x
        draw_y = state.y - cam_y

        if state.is_moving:
            rotated_player = pygame.transform.rotate(self.brain_moving_img, -state.angle)
        else:
            rotated_player = pygame.transform.rotate(self.brain_stopped_img, -state.angle)
        rect = rotated_player.get_rect(center=(draw_x, draw_y))
        surface.blit(rotated_player, rect.topleft)

        if ski_config.debug_colliders:
            debug_player_color = (0, 255, 0)  # Green
            debug_obs_color = (255, 0, 0)  # Red
            debug_wall_color = (0, 255, 255)  # Cyan

            draw_rad = math.radians(state.angle)
            d_cos = math.cos(draw_rad)
            d_sin = math.sin(draw_rad)

            def local_to_screen(lx: float, ly: float) -> tuple[int, int]:
                rx = lx * d_cos - ly * d_sin
                ry = lx * d_sin + ly * d_cos
                return int(player_draw_x + rx), int(player_draw_y + ry)

            hw1 = ski_config.player_box1_width / 2.0
            hh1 = ski_config.player_box1_height / 2.0
            ox1 = ski_config.player_box1_offset_x
            oy1 = ski_config.player_box1_offset_y

            pts1 = [
                local_to_screen(ox1 - hw1, oy1 - hh1),
                local_to_screen(ox1 + hw1, oy1 - hh1),
                local_to_screen(ox1 + hw1, oy1 + hh1),
                local_to_screen(ox1 - hw1, oy1 + hh1),
            ]
            pygame.draw.polygon(surface, debug_player_color, pts1, width=2)

            hw2 = ski_config.player_box2_width / 2.0
            hh2 = ski_config.player_box2_height / 2.0
            ox2 = ski_config.player_box2_offset_x
            oy2 = ski_config.player_box2_offset_y

            pts2 = [
                local_to_screen(ox2 - hw2, oy2 - hh2),
                local_to_screen(ox2 + hw2, oy2 - hh2),
                local_to_screen(ox2 + hw2, oy2 + hh2),
                local_to_screen(ox2 - hw2, oy2 + hh2),
            ]
            pygame.draw.polygon(surface, debug_player_color, pts2, width=2)

            for obs in state.obstacles:
                obs_draw_x = obs.x - cam_x
                obs_draw_y = obs.y - cam_y

                if obs.speed > 0:
                    sx = int(obs_draw_x + ski_config.dynamic_sphere_offset_x)
                    sy = int(obs_draw_y + ski_config.dynamic_sphere_offset_y)
                    sr = int(ski_config.dynamic_sphere_radius)
                    pygame.draw.circle(surface, debug_obs_color, (sx, sy), sr, width=2)

                    x1 = obs_draw_x + ski_config.dynamic_capsule_p1_x
                    y1 = obs_draw_y + ski_config.dynamic_capsule_p1_y
                    x2 = obs_draw_x + ski_config.dynamic_capsule_p2_x
                    y2 = obs_draw_y + ski_config.dynamic_capsule_p2_y
                    cr = int(ski_config.dynamic_capsule_radius)

                    pygame.draw.circle(surface, debug_obs_color, (int(x1), int(y1)), cr, width=2)
                    pygame.draw.circle(surface, debug_obs_color, (int(x2), int(y2)), cr, width=2)

                    dx, dy = x2 - x1, y2 - y1
                    length = math.hypot(dx, dy)
                    if length > 0:
                        nx = (dy / length) * cr
                        ny = (-dx / length) * cr

                        pygame.draw.line(
                            surface,
                            debug_obs_color,
                            (int(x1 + nx), int(y1 + ny)),
                            (int(x2 + nx), int(y2 + ny)),
                            width=2,
                        )
                        pygame.draw.line(
                            surface,
                            debug_obs_color,
                            (int(x1 - nx), int(y1 - ny)),
                            (int(x2 - nx), int(y2 - ny)),
                            width=2,
                        )

                else:
                    cx = int(obs_draw_x + ski_config.obstacle_collider_offset_x)
                    cy = int(obs_draw_y + ski_config.obstacle_collider_offset_y)
                    r = int(ski_config.obstacle_collider_radius)

                    pygame.draw.circle(surface, debug_obs_color, (cx, cy), r, width=2)

            screen_w = Grid.x(12)
            margin = ski_config.track_margin_px
            b_vis_rad = ski_config.barrier_radius
            b_pad = ski_config.barrier_transparent_padding

            left_wall_world_x = margin + b_vis_rad + (b_vis_rad - b_pad)
            right_wall_world_x = screen_w - margin - b_vis_rad - (b_vis_rad - b_pad)
            top_wall_world_y = state.goal_y - ski_config.track_top_margin + (b_vis_rad - b_pad)
            bottom_wall_world_y = state.start_y + ski_config.track_bottom_margin - (b_vis_rad - b_pad)

            left_wall_draw_x = int(left_wall_world_x - cam_x)
            right_wall_draw_x = int(right_wall_world_x - cam_x)
            top_wall_draw_y = int(top_wall_world_y - cam_y)
            bottom_wall_draw_y = int(bottom_wall_world_y - cam_y)

            pygame.draw.line(
                surface,
                debug_wall_color,
                (left_wall_draw_x, top_wall_draw_y),
                (left_wall_draw_x, bottom_wall_draw_y),
                2,
            )
            pygame.draw.line(
                surface,
                debug_wall_color,
                (right_wall_draw_x, top_wall_draw_y),
                (right_wall_draw_x, bottom_wall_draw_y),
                2,
            )
            pygame.draw.line(
                surface, debug_wall_color, (left_wall_draw_x, top_wall_draw_y), (right_wall_draw_x, top_wall_draw_y), 2
            )
            pygame.draw.line(
                surface,
                debug_wall_color,
                (left_wall_draw_x, bottom_wall_draw_y),
                (right_wall_draw_x, bottom_wall_draw_y),
                2,
            )

        score_txt = SUBTEXT_FONT.render(f"Score: {state.score:.1f}", True, TEXT_COLOR)
        surface.blit(score_txt, score_txt.get_rect(topright=(Grid.x(11.5), Grid.y(0.4))))

        time_txt = SUBTEXT_FONT.render(f"Time: {state.time_left:.1f}s", True, TEXT_COLOR)
        surface.blit(time_txt, time_txt.get_rect(topright=(Grid.x(11.5), Grid.y(1.2))))

        bonus_txt = SUBTEXT_FONT.render(f"Time Bonus: +{state.current_time_bonus:.0f}", True, TEXT_COLOR)
        surface.blit(bonus_txt, bonus_txt.get_rect(topright=(Grid.x(11.5), Grid.y(2.0))))

        if state.game_over:
            go_txt = SUBTEXT_FONT.render("GAME OVER", True, (255, 0, 0))
            surface.blit(go_txt, go_txt.get_rect(center=(Grid.x(6), Grid.y(4))))

        self._draw_roadmap(surface, state)

        if overlay is not None:
            overlay(surface)
        scale_to_screen(surface, screen)
