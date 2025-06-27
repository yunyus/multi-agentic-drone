# FILE: simulation_logger.py
import json
from config import GRID_WIDTH, GRID_HEIGHT

class SimulationLogger:
    """
    Handles logging the entire state of the simulation to a JSON file.
    The log file is updated dynamically after every tick.
    """
    def __init__(self, filename="simulation_log.json"):
        self.filename = filename
        self.log_data = {
            "initial_state": {},
            "tick_data": []
        }
        # Başlangıçta boş bir dosya oluştur
        self._save_to_file()
        print(f"Logger initialized. Log file '{self.filename}' will be updated dynamically.")

    def _save_to_file(self):
        """
        Bu iç metot, mevcut log verisini dosyaya yazar.
        Artık her veri eklendiğinde çağrılır.
        """
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.log_data, f, indent=2)
        except Exception as e:
            # Hata durumunda hangi verinin sorun çıkardığını anlamak için daha detaylı loglama
            print(f"Error saving log file: {e}")
            # print("Problematic data:", self.log_data) # Hata ayıklama için bu satırı açabilirsiniz

    def log_initial_state(self, grid):
        """
        Logs the static elements of the map once at the beginning of the simulation.
        Includes grid size, obstacles, base boundaries, stationary enemies, and HSS locations.
        """
        base_min_x, base_max_x = GRID_WIDTH, -1
        base_min_y, base_max_y = GRID_HEIGHT, -1

        initial_state = {
            "grid_size": {"width": GRID_WIDTH, "height": GRID_HEIGHT},
            "obstacles": [],
            "stationary_enemies": [],
            "hss_systems": []
        }

        for x in range(grid.width):
            for y in range(grid.height):
                tile = grid.get_tile(x, y)
                pos = {"x": x, "y": y}
                if tile.type == 'BASE':
                    base_min_x = min(base_min_x, x)
                    base_max_x = max(base_max_x, x)
                    base_min_y = min(base_min_y, y)
                    base_max_y = max(base_max_y, y)
                elif tile.type == 'OBSTACLE':
                    initial_state["obstacles"].append(pos)
                elif tile.type == 'STATIONARY_ENEMY':
                    initial_state["stationary_enemies"].append({
                        "id": tile.properties.get('enemy_id'),
                        "position": pos
                    })
                elif tile.type == 'HSS':
                    initial_state["hss_systems"].append({
                        "id": tile.properties.get('hss_id'),
                        "position": pos,
                        "radius": tile.properties.get('kill_zone_radius')
                    })
        
        if base_max_x != -1:
            initial_state["base_bounds"] = {
                "min_x": base_min_x, "max_x": base_max_x,
                "min_y": base_min_y, "max_y": base_max_y
            }

        self.log_data["initial_state"] = initial_state
        self._save_to_file()
        print("Initial map state logged and saved.")

    def log_tick_state(self, tick, drones, moving_enemies, active_missiles):
        """
        Logs the state of all dynamic actors for a given tick and saves to file.
        """
        tick_state = {
            "tick": tick,
            "drones": [],
            "moving_enemies": [],
            "missiles": []
        }

        for drone in drones:
            # YENİ: Komutu loglamadan önce JSON ile uyumsuz olabilecek veya
            # log dosyasını şişirecek alanları temizle.
            loggable_command = drone.current_command.copy()
            loggable_command.pop('known_tiles', None)  # tuple key içeren sözlüğü kaldır
            loggable_command.pop('threat_zones', None) # Büyük listeyi kaldır

            tick_state["drones"].append({
                "id": drone.id, "position": drone.position.copy(),
                "battery": round(drone.battery, 2), "status": drone.status,
                "scan_mode": drone.scan_mode,
                "current_command": loggable_command # Temizlenmiş komutu logla
            })

        for enemy in moving_enemies:
            tick_state["moving_enemies"].append({
                "id": enemy.id, "position": enemy.position.copy(),
                "status": enemy.status
            })
        for missile in active_missiles:
            tick_state["missiles"].append({
                "current_position": missile.current_position.copy(),
                "target_position": missile.target_position.copy(),
                "status": missile.status, "path_length": len(missile.path)
            })
            
        self.log_data["tick_data"].append(tick_state)
        self._save_to_file()

    def close(self):
        """This method is no longer necessary as logging is dynamic."""
        print("Logger is closing. Final log state is already saved.")