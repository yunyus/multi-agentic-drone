# FILE: enemy.py
import random
from config import GRID_WIDTH, GRID_HEIGHT, MOVING_ENEMY_SPEED

class MovingEnemy:
    """A moving enemy that drones can hunt."""
    def __init__(self, enemy_id, grid):
        self.id = enemy_id
        self.grid = grid
        # Spawn away from the base
        self.position = {
            'x': random.randint(int(GRID_WIDTH / 2), GRID_WIDTH - 1),
            'y': random.randint(int(GRID_HEIGHT / 2), GRID_HEIGHT - 1)
        }
        self.status = 'ACTIVE' # 'ACTIVE' or 'DESTROYED'
        self.speed = MOVING_ENEMY_SPEED
        # Calculate how many ticks to wait between moves based on speed
        self._move_tick_interval = int(1 / self.speed) if self.speed > 0 else float('inf')

    def update(self, current_tick):
        """Updates the enemy's state, primarily its movement."""
        if self.status != 'ACTIVE':
            return

        # Move only on the specified tick interval
        if current_tick % self._move_tick_interval == 0:
            self.move()

    def move(self):
        """Moves randomly by one tile, avoiding obstacles and the base."""
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)] # 4 directions for simpler movement
        random.shuffle(directions)
        
        for dx, dy in directions:
            next_x = self.position['x'] + dx
            next_y = self.position['y'] + dy

            # Check bounds
            if 0 <= next_x < GRID_WIDTH and 0 <= next_y < GRID_HEIGHT:
                tile = self.grid.get_tile(next_x, next_y)
                # Ensure it doesn't move into an obstacle or the base
                if tile and tile.type not in ['OBSTACLE', 'BASE']:
                    self.position['x'] = next_x
                    self.position['y'] = next_y
                    break # Move was successful, exit loop