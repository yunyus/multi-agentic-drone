# FILE: visualizer.py
from config import *

if ENABLE_VISUALIZATION:
    import pygame

class Visualizer:
    def __init__(self, engine):
        if not ENABLE_VISUALIZATION: return
        pygame.init()
        pygame.display.set_caption("Strategist Drone Simulation")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.font = pygame.font.SysFont('Arial', 12, bold=True)
        self.engine = engine

    def draw(self):
        if not ENABLE_VISUALIZATION: return
        self.screen.fill(COLOR_BG)
        self.draw_grid_and_threats()
        self.draw_known_world()
        self.draw_missiles()
        self.draw_moving_enemies()
        self.draw_drones()
        self.draw_info()
        pygame.display.flip()

    def draw_grid_and_threats(self):
        # Draw known HSS danger zones
        for zone in self.engine.central_strategist.world_model['potential_threat_zones']:
            if 'hss_location' in zone:
                hss_x, hss_y, r = zone['hss_location']['x'], zone['hss_location']['y'], zone['radius']
                px, py = hss_x * CELL_SIZE + CELL_SIZE // 2, (GRID_HEIGHT - 1 - hss_y) * CELL_SIZE + CELL_SIZE // 2
                pr = r * CELL_SIZE
                s = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, COLOR_HSS_RANGE, (pr, pr), pr)
                self.screen.blit(s, (px - pr, py - pr))

        # Draw tiles
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                rect = pygame.Rect(x * CELL_SIZE, (GRID_HEIGHT - 1 - y) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                tile = self.engine.grid.get_tile(x, y)
                if tile.type == 'OBSTACLE':
                    pygame.draw.rect(self.screen, COLOR_OBSTACLE, rect)
                elif tile.type == 'STATIONARY_ENEMY':
                    center_pixel_x = rect.centerx
                    center_pixel_y = rect.centery
                    pygame.draw.line(self.screen, COLOR_STATIONARY_ENEMY, (rect.left, rect.top), (rect.right, rect.bottom), 2)
                    pygame.draw.line(self.screen, COLOR_STATIONARY_ENEMY, (rect.left, rect.bottom), (rect.right, rect.top), 2)
                elif tile.type == 'BASE':
                    s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                    s.fill(COLOR_BASE)
                    self.screen.blit(s, rect.topleft)

    def draw_known_world(self):
        s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        s.fill(COLOR_KNOWN_WORLD)
        for x, y in self.engine.central_strategist.world_model['known_tiles']:
            rect = pygame.Rect(x * CELL_SIZE, (GRID_HEIGHT - 1 - y) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            self.screen.blit(s, rect.topleft)

    def draw_drones(self):
        for drone in self.engine.drones:
            x, y = drone.position['x'], drone.position['y']
            center = (x * CELL_SIZE + CELL_SIZE // 2, (GRID_HEIGHT - 1 - y) * CELL_SIZE + CELL_SIZE // 2)
            color = COLOR_DRONE if drone.status != 'DESTROYED' else COLOR_DRONE_DESTROYED
            pygame.draw.circle(self.screen, color, center, CELL_SIZE // 2)

    def draw_moving_enemies(self):
        for enemy in self.engine.moving_enemies:
            if enemy.status == 'ACTIVE':
                x, y = enemy.position['x'], enemy.position['y']
                center = (x * CELL_SIZE + CELL_SIZE // 2, (GRID_HEIGHT - 1 - y) * CELL_SIZE + CELL_SIZE // 2)
                points = [(center[0], center[1] - CELL_SIZE // 2), (center[0] - CELL_SIZE // 2, center[1] + CELL_SIZE // 2), (center[0] + CELL_SIZE // 2, center[1] + CELL_SIZE // 2)]
                pygame.draw.polygon(self.screen, COLOR_MOVING_ENEMY, points)

    def draw_missiles(self):
        for missile in self.engine.active_missiles:
            # Draw missile path
            path_points = [missile.current_position] + missile.path
            if len(path_points) > 1:
                pixel_points = [(p['x'] * CELL_SIZE + CELL_SIZE // 2, (GRID_HEIGHT - 1 - p['y']) * CELL_SIZE + CELL_SIZE // 2) for p in path_points]
                pygame.draw.lines(self.screen, COLOR_MISSILE_PATH, False, pixel_points, 1)
            # Draw missile
            x, y = missile.current_position['x'], missile.current_position['y']
            center = (x * CELL_SIZE + CELL_SIZE // 2, (GRID_HEIGHT - 1 - y) * CELL_SIZE + CELL_SIZE // 2)
            pygame.draw.circle(self.screen, COLOR_MISSILE, center, CELL_SIZE // 2 - 1)
    
    def draw_info(self):
        active_stationary = sum(1 for r in self.engine.grid.tiles for t in r if t.type == 'STATIONARY_ENEMY')
        active_moving = sum(1 for e in self.engine.moving_enemies if e.status == 'ACTIVE')
        info_texts = [
            f"Tick: {self.engine.current_tick}",
            f"Missiles Left: {self.engine.missile_system.missile_count}",
            f"Active Drones: {sum(1 for d in self.engine.drones if d.status != 'DESTROYED')}/{NUM_DRONES}",
            f"Stationary Enemies: {active_stationary}/{NUM_STATIONARY_ENEMIES}",
            f"Moving Enemies: {active_moving}/{NUM_MOVING_ENEMIES}",
        ]
        for i, text in enumerate(info_texts):
            text_surf = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(text_surf, (5, 5 + i * 15))