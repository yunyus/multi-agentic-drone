# FILE: grid.py
import random
from config import *

class Tile:
    """Represents a single tile on the map."""
    def __init__(self, x, y, tile_type='EMPTY', properties=None):
        self.x = x
        self.y = y
        self.type = tile_type  # 'EMPTY', 'OBSTACLE', 'BASE', 'STATIONARY_ENEMY', 'HSS'
        self.properties = properties if properties else {}
        self.is_known_by_strategist = False

class Grid:
    """Manages the game area and static objects on it."""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.tiles = [[Tile(x, y) for y in range(height)] for x in range(width)]
        self._generate_map()

    def _generate_map(self):
        # Base Area
        for x in range(11):
            for y in range(11):
                self.tiles[x][y].type = 'BASE'

        for _ in range(NUM_OBSTACLE_BLOCKS):
            # Engel bloğunun boyutlarını rastgele belirle
            block_width = random.randint(MIN_BLOCK_WIDTH, MAX_BLOCK_WIDTH)
            block_height = random.randint(MIN_BLOCK_HEIGHT, MAX_BLOCK_HEIGHT)
            
            # Engel bloğunun sol alt köşesi için rastgele bir başlangıç noktası seç.
            # Üs bölgesinin (0-10, 0-10) ve harita sınırlarının dışına taşmamasına dikkat et.
            # Üs bölgesine çok yakın başlamasını engellemek için başlangıç koordinatlarını 11'den başlatabiliriz.
            start_x = random.randint(11, self.width - block_width - 1)
            start_y = random.randint(11, self.height - block_height - 1)
            
            # Belirlenen alandaki tüm tile'ları 'OBSTACLE' olarak işaretle
            is_valid_location = True
            # Yerleştirmeden önce alanın boş olup olmadığını kontrol et (opsiyonel ama iyi bir pratik)
            for x in range(start_x, start_x + block_width):
                for y in range(start_y, start_y + block_height):
                    if self.tiles[x][y].type != 'EMPTY':
                        is_valid_location = False
                        break
                if not is_valid_location:
                    break
            
            # Eğer alan müsaitse, engelleri yerleştir
            if is_valid_location:
                for x in range(start_x, start_x + block_width):
                    for y in range(start_y, start_y + block_height):
                        self.tiles[x][y].type = 'OBSTACLE'
        
        # Stationary Enemies
        for i in range(NUM_STATIONARY_ENEMIES):
            while True:
                x, y = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
                if self.tiles[x][y].type == 'EMPTY':
                    self.tiles[x][y].type = 'STATIONARY_ENEMY'
                    self.tiles[x][y].properties = {"enemy_id": f"SE-{i+1}", "status": "ACTIVE"}
                    break
        
        # HSS (Hidden Air Defense Systems)
        for i in range(NUM_HSS):
            while True:
                x, y = random.randint(15, self.width - 15), random.randint(15, self.height - 15)
                if self.tiles[x][y].type == 'EMPTY':
                    self.tiles[x][y].type = 'HSS'
                    self.tiles[x][y].properties = {"hss_id": f"HSS-{i+1}", "kill_zone_radius": random.randint(5, 8)}
                    break

    def get_tile(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[x][y]
        return None

    def get_visible_tiles(self, x, y, radius):
        """Finds visible tiles using Line-of-Sight algorithm."""
        visible_tiles = []
        center_tile = self.get_tile(x, y)
        if center_tile:
            visible_tiles.append(center_tile)

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) + abs(dy) > radius:
                    continue
                
                target_x, target_y = x + dx, y + dy
                if not (0 <= target_x < self.width and 0 <= target_y < self.height):
                    continue

                # Bresenham's Line Algorithm for line-of-sight check
                line_x, line_y = x, y
                d_x, d_y = target_x - line_x, target_y - line_y
                step_x = 1 if d_x > 0 else -1
                step_y = 1 if d_y > 0 else -1
                d_x, d_y = abs(d_x), abs(d_y)
                
                error = d_x - d_y
                is_blocked = False
                
                while line_x != target_x or line_y != target_y:
                    if self.get_tile(line_x, line_y).type == 'OBSTACLE' and (line_x != x or line_y != y):
                        is_blocked = True
                        break
                    
                    e2 = 2 * error
                    if e2 > -d_y:
                        error -= d_y
                        line_x += step_x
                    if e2 < d_x:
                        error += d_x
                        line_y += step_y
                
                if not is_blocked:
                    visible_tiles.append(self.get_tile(target_x, target_y))

        return visible_tiles