from config import INITIAL_MISSILES

class MissileSystem:
    """Manages missile inventory and firing commands."""
    def __init__(self, grid):
        self.missile_count = INITIAL_MISSILES
        self.grid = grid

    def fire(self, target_coord):
        if self.missile_count > 0:
            x, y = target_coord['x'], target_coord['y']
            tile = self.grid.get_tile(x, y)
            if tile and tile.type == 'TARGET':
                print(f"MISSILE FIRED: {tile.properties['target_id']} at ({x}, {y}) destroyed!")
                tile.type = 'EMPTY'
                tile.properties = {}
                self.missile_count -= 1
                return True
            else:
                print(f"MISSILE FIRED BUT NO TARGET FOUND: ({x}, {y})")
                self.missile_count -= 1
                return False
        print("NO MISSILES LEFT!")
        return False 