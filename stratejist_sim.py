import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")


import openai
import json
import math
import random
import time
import os


# Simülasyon Ayarları
GRID_WIDTH = 100
GRID_HEIGHT = 100
NUM_DRONES = 10
NUM_TARGETS = 3
NUM_HSS = 4 # Gizli Hava Savunma Sistemleri
INITIAL_MISSILES = 5

# LLM Ayarları
LLM_MODEL = "gpt-4o"
# API çağrılarını atlayıp test için sahte bir yanıt kullanmak isterseniz True yapın
MOCK_LLM_RESPONSE = False 

# Drone Ayarları
DRONE_BATTERY_MAX = 1000.0
DRONE_SCAN_RADIUS = 5 # Manhattan mesafesi
COST_MOVE = 1.0
COST_SCAN = 5.0
COST_REPORT = 2.0
BASE_RECHARGE_RATE = 50.0

# Görselleştirme Ayarları (Pygame)
ENABLE_VISUALIZATION = True
if ENABLE_VISUALIZATION:
    import pygame
    CELL_SIZE = 8
    SCREEN_WIDTH = GRID_WIDTH * CELL_SIZE
    SCREEN_HEIGHT = GRID_HEIGHT * CELL_SIZE
    FPS = 10 # Simülasyon hızını kontrol eder

    # Renkler
    COLOR_BG = (10, 10, 20)
    COLOR_GRID = (40, 40, 50)
    COLOR_EMPTY = (25, 25, 40)
    COLOR_OBSTACLE = (100, 100, 100)
    COLOR_BASE = (0, 150, 50, 100)
    COLOR_TARGET = (255, 0, 0)
    COLOR_HSS = (255, 100, 0) # Sadece debug için
    COLOR_DRONE = (0, 200, 255)
    COLOR_DRONE_DESTROYED = (150, 0, 0)
    COLOR_SCAN_AREA = (255, 255, 0, 50)
    COLOR_KNOWN_WORLD = (0, 155, 0, 30) # Stratejistin bildiği alan
    COLOR_HSS_RANGE = (255, 100, 0, 60) 


# --- 2. Sistem Mimarisi ve Bileşenler ---

class Tile:
    """Haritadaki tek bir karoyu temsil eder."""
    def __init__(self, x, y, tile_type='EMPTY', properties=None):
        self.x = x
        self.y = y
        self.type = tile_type  # 'EMPTY', 'OBSTACLE', 'BASE', 'TARGET', 'HSS'
        self.properties = properties if properties else {}
        self.is_known_by_strategist = False

class Grid:
    """Oyun alanını ve üzerindeki statik nesneleri yönetir."""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.tiles = [[Tile(x, y) for y in range(height)] for x in range(width)]
        self._generate_map()

    def _generate_map(self):
        # Üs Bölgesi
        for x in range(11):
            for y in range(11):
                self.tiles[x][y].type = 'BASE'

        # Engeller (azaltıldı)
        for _ in range(int(self.width * self.height * 0.01)): # Haritanın %5'i engel olsun
            x, y = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
            if self.tiles[x][y].type == 'EMPTY':
                self.tiles[x][y].type = 'OBSTACLE'
        
        # Hedefler
        for i in range(NUM_TARGETS):
            while True:
                x, y = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
                if self.tiles[x][y].type == 'EMPTY':
                    self.tiles[x][y].type = 'TARGET'
                    self.tiles[x][y].properties = {"target_id": f"Hedef-{i+1}", "status": "ACTIVE"}
                    break
        
        # HSS (Gizli Hava Savunma Sistemleri)
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
        """Line-of-Sight (Görüş Hattı) algoritması ile görünür karoları bulur."""
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

                # Bresenham's Line Algorithm ile görüş hattı kontrolü
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

class MissileSystem:
    """Füze envanterini tutar ve ateşleme komutlarını uygular."""
    def __init__(self, grid):
        self.missile_count = INITIAL_MISSILES
        self.grid = grid

    def fire(self, target_coord):
        if self.missile_count > 0:
            x, y = target_coord['x'], target_coord['y']
            tile = self.grid.get_tile(x, y)
            if tile and tile.type == 'TARGET':
                print(f"FÜZE ATEŞLENDİ: ({x}, {y}) koordinatındaki {tile.properties['target_id']} imha edildi!")
                tile.type = 'EMPTY'
                tile.properties = {}
                self.missile_count -= 1
                return True
            else:
                print(f"FÜZE ATEŞLENDİ AMA HEDEF BULUNAMADI: ({x}, {y})")
                self.missile_count -= 1
                return False
        print("FÜZE KALMADI!")
        return False

class DroneAgent:
    """Harita üzerinde hareket eden, sensör verisi toplayan bireysel birim."""
    def __init__(self, drone_id, grid):
        self.id = drone_id
        self.grid = grid
        self.position = {'x': random.randint(1, 9), 'y': random.randint(1, 9)}
        self.battery = DRONE_BATTERY_MAX
        self.status = 'ACTIVE' # 'ACTIVE', 'RECHARGING', 'DESTROYED'
        self.current_command = {"command_type": "STANDBY"}
        self.scan_results = []
        self.scan_mode = 'PASSIVE' # 'ACTIVE' veya 'PASSIVE'
        self.path = [] # A* path finding için
        self.known_tiles = {} # Drone'un bildiği tile'lar (stratejist'ten alınır)

    def set_command(self, command):
        self.current_command = command
        # Scan mode komutunu ayrı olarak işle
        if 'scan_mode' in command:
            self.scan_mode = command['scan_mode']
            print(f"{self.id} scan mode güncellendi: {self.scan_mode}")
        # Known tiles güncellemesi (stratejist'ten gelen bilgi)
        if 'known_tiles' in command:
            self.known_tiles = command['known_tiles']
            print(f"{self.id} harita bilgisi güncellendi: {len(self.known_tiles)} karo biliniyor")

    def update(self):
        """Her tick'te çağrılan ana güncelleme metodu."""
        if self.status != 'ACTIVE':
            return
        
        self.execute_command()
        
        # Pil biterse
        if self.battery <= 0:
            print(f"UYARI: {self.id} pili bitti ve yok oldu!")
            self.status = 'DESTROYED'

    def execute_command(self):
        """Merkez'den gelen komutu işler."""
        cmd_type = self.current_command.get('command_type')

        if cmd_type == 'MOVE_DRONE':
            target_pos = self.current_command.get('target_position')
            if target_pos:
                self.move(target_pos)
        elif cmd_type == 'SCAN_AREA':
            self.scan()
        elif cmd_type == 'STANDBY':
            # Üs bölgesindeyse ve pili azsa şarj ol
            tile = self.grid.get_tile(self.position['x'], self.position['y'])
            if tile.type == 'BASE' and self.battery < DRONE_BATTERY_MAX:
                self.recharge()
            else:
                pass # Bekle

    def move(self, target_position):
        """Belirtilen hedefe doğru path finding ile hareket eder."""
        target_x, target_y = target_position['x'], target_position['y']
        
        if self.position['x'] == target_x and self.position['y'] == target_y: # Hedefe ulaşıldı
            self.path = []  # Path'i temizle
            # Hedefe ulaştıktan sonra scan mode kontrol et
            if self.scan_mode == 'ACTIVE':
                print(f"{self.id} hedefe ulaştı ve otomatik tarama yapıyor (ACTIVE mode)")
                self.scan()
            else:
                self.current_command = {"command_type": "STANDBY"} # Yeni komut bekle
            return

        # Path yoksa veya geçerli değilse yeni path hesapla
        if not self.path or not self._is_path_valid():
            self.path = self._find_path_to_target(target_x, target_y)
            if not self.path:
                print(f"{self.id} hedefe ({target_x},{target_y}) path bulunamadı, bekliyor.")
                self.current_command = {"command_type": "STANDBY"}
                return

        # Path'teki bir sonraki pozisyona git
        if self.path:
            next_pos = self.path.pop(0)
            next_x, next_y = next_pos['x'], next_pos['y']
            
            # Ground truth kontrolü (gerçek collision detection)
            tile = self.grid.get_tile(next_x, next_y)
            if tile and tile.type != 'OBSTACLE':
                self.position['x'] = next_x
                self.position['y'] = next_y
                self.battery -= COST_MOVE
                
                # ACTIVE scan mode ise her hareket sonrası tarama yap
                if self.scan_mode == 'ACTIVE' and random.random() < 0.3: # %30 şans ile tarama
                    print(f"{self.id} hareket ederken çevreyi taradı (ACTIVE mode)")
                    self.scan()
            else:
                # Gerçek engele çarptı (bilinmeyen engel keşfedildi)
                print(f"{self.id} bilinmeyen engele çarptı ({next_x},{next_y}), yeni rota hesaplıyor.")
                # Bu engeli known_tiles'a ekle (keşfedildi)
                self.known_tiles[(next_x, next_y)] = {'type': 'OBSTACLE', 'position': {'x': next_x, 'y': next_y}}
                self.path = []

    def _is_path_valid(self):
        """Mevcut path'in hala geçerli olup olmadığını kontrol eder."""
        for pos in self.path:
            tile = self.grid.get_tile(pos['x'], pos['y'])
            if not tile or tile.type == 'OBSTACLE':
                return False
        return True

    def _find_path_to_target(self, target_x, target_y):
        """A* benzeri basit path finding algoritması."""
        from collections import deque
        
        start = (self.position['x'], self.position['y'])
        target = (target_x, target_y)
        
        if start == target:
            return []
        
        # BFS ile path bulma (A* yerine daha basit)
        queue = deque([(start, [])])
        visited = {start}
        
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]  # 8 yön
        
        while queue:
            (x, y), path = queue.popleft()
            
            # Hedefe ulaştık mı?
            if (x, y) == target:
                return [{'x': px, 'y': py} for px, py in path]
            
            # Path çok uzarsa durabilir (performans için)
            if len(path) > 50:
                continue
            
            # Komşuları kontrol et
            for dx, dy in directions:
                next_x, next_y = x + dx, y + dy
                
                if (next_x, next_y) in visited:
                    continue
                    
                # Harita sınırları kontrolü
                if not (0 <= next_x < self.grid.width and 0 <= next_y < self.grid.height):
                    continue
                
                tile = self.grid.get_tile(next_x, next_y)
                if not tile:
                    continue
                
                # Bilinen engelleri kontrol et
                if self._is_known_obstacle(next_x, next_y):
                    continue
                
                visited.add((next_x, next_y))
                new_path = path + [(next_x, next_y)]
                queue.append(((next_x, next_y), new_path))
        
        # Path bulunamadı
        return []

    def _is_known_obstacle(self, x, y):
        """Drone'un bildiği engelleri kontrol eder (sadece known tiles)."""
        # Sadece bilinen tile'lardaki engelleri kontrol et
        tile_key = (x, y)
        if tile_key in self.known_tiles:
            tile_data = self.known_tiles[tile_key]
            return tile_data.get('type') == 'OBSTACLE'
        
        # Bilinmeyen tile'lar engel değil (geçilebilir kabul edilir)
        return False

    def scan(self):
        self.scan_results = self.grid.get_visible_tiles(
            self.position['x'], self.position['y'], DRONE_SCAN_RADIUS
        )
        self.battery -= COST_SCAN
        print(f"{self.id} pozisyon ({self.position['x']},{self.position['y']}) civarını taradı. {len(self.scan_results)} karo bulundu.")
        # Tarama sonrası yeni komut bekle
        self.current_command = {"command_type": "STANDBY"}

    def recharge(self):
        self.battery = min(DRONE_BATTERY_MAX, self.battery + BASE_RECHARGE_RATE)
        print(f"{self.id} üs bölgesinde şarj oluyor. Mevcut Pil: {self.battery:.1f}")

    def report_to_center(self):
        """Mevcut durumunu ve tarama sonuçlarını JSON formatında hazırlar."""
        if self.status == 'DESTROYED':
            return None

        report = {
            "drone_id": self.id,
            "status": self.status,
            "position": self.position,
            "battery": round(self.battery, 2),
            "scan_results": []
        }
        
        for tile in self.scan_results:
            tile_data = {
                "type": tile.type if tile.type != 'HSS' else 'EMPTY', # HSS'ler taramada görünmez
                "position": {"x": tile.x, "y": tile.y}
            }
            if tile.type == 'TARGET':
                tile_data["properties"] = tile.properties
            report["scan_results"].append(tile_data)
            
            # Tarama sonuçlarını kendi known_tiles'ına da ekle
            self.known_tiles[(tile.x, tile.y)] = tile_data

        self.battery -= COST_REPORT
        self.scan_results = []  # Raporlandıktan sonra tarama sonuçlarını temizle
        return report

class CentralStrategist:
    """Tüm drone'lardan gelen bilgiyi toplar, GPT-4o ile plan yapar ve komut gönderir."""
    def __init__(self, grid):
        self.llm_api_key = API_KEY
        self.llm_model = LLM_MODEL
        self.client = openai.OpenAI(api_key=self.llm_api_key)
        self.grid = grid
        # Dünya modeli: Stratejistin bildiği her şey burada tutulur
        self.world_model = {
            "grid_size": {"width": GRID_WIDTH, "height": GRID_HEIGHT},
            "base_location": {"x_range": [0, 10], "y_range": [0, 10]},
            "known_tiles": {}, # (x, y) -> Tile
            "known_targets": {}, # target_id -> {"position": ..., "status": ...}
            "potential_threat_zones": [] # HSS şüpheleri
        }

    def collect_reports(self, reports):
        """Drone raporlarını alıp dünya modelini günceller."""
        for report in reports:
            if not report: continue
            # Tarama sonuçlarını işle
            for tile_data in report['scan_results']:
                x, y = tile_data['position']['x'], tile_data['position']['y']
                
                # Dünya modeline ekle
                if (x,y) not in self.world_model['known_tiles']:
                     self.world_model['known_tiles'][(x,y)] = tile_data

                self.grid.get_tile(x, y).is_known_by_strategist = True

                if tile_data['type'] == 'TARGET':
                    target_id = tile_data['properties']['target_id']
                    if target_id not in self.world_model['known_targets']:
                        print(f"STRATEJİST: Yeni hedef bulundu! {target_id} at ({x},{y})")
                        self.world_model['known_targets'][target_id] = {
                            "position": tile_data['position'],
                            "status": "CONFIRMED"
                        }
    
    def add_threat_zone(self, position):
        zone = {"center": position, "radius": 10, "confidence": "HIGH"}
        self.world_model['potential_threat_zones'].append(zone)
        print(f"STRATEJİST: Yeni tehlike bölgesi eklendi: {position}")

    def _format_state_for_llm(self, tick, drones, missile_system):
        """Mevcut dünya modelini LLM'e göndermek için JSON formatına çevirir."""
        
        # Bilinen engelleri ve hedefleri işle
        known_obstacles = []
        for (x,y), tile in self.world_model['known_tiles'].items():
            if tile['type'] == 'OBSTACLE':
                known_obstacles.append({'x': x, 'y': y})
        
        known_targets_list = [
            {"id": tid, **tdata} for tid, tdata in self.world_model['known_targets'].items()
        ]

        drones_state = []
        for d in drones:
            state = {"id": d.id, "status": d.status, "battery": round(d.battery, 2), "scan_mode": d.scan_mode}
            if d.status == 'DESTROYED':
                state["last_known_position"] = d.position
            else:
                state["position"] = d.position
            drones_state.append(state)

        state_json = {
            "tick": tick,
            "mission_objective": "Tüm 3 hedefi yok et. Bilinmeyen HSS'lerden kaçınarak drone kayıplarını en aza indir.",
            "resources": {
                "missiles_left": missile_system.missile_count
            },
            "drones": drones_state,
            "known_world": {
                "grid_size": self.world_model['grid_size'],
                "base_location": self.world_model['base_location'],
                "known_obstacles": known_obstacles,
                "known_targets": known_targets_list,
                "potential_threat_zones": self.world_model['potential_threat_zones']
            }
        }
        return state_json

    def plan_next_moves(self, current_tick, drones, missile_system):
        """LLM'e istek gönderir ve geri dönen komutları ayrıştırır."""
        world_state = self._format_state_for_llm(current_tick, drones, missile_system)
        
        system_prompt = """
# ROLE AND GOAL
You are "Stratejist", a central command AI for a swarm of 10 autonomous drones. Your mission is to explore a 100x100 grid map, identify all 3 enemy targets, and destroy them using a limited supply of 5 missiles. You must achieve this while minimizing drone losses to hidden Hostile Air Defense Systems (HSS).

# RULES
1.  **Map:** The map is a 100x100 grid. (0,0) is the bottom-left. Your base is at (0,0) to (10,10).
2.  **Drones:** Drones consume battery for every action. They can recharge at the Base. Send them to base if battery is low (e.g., < 200). Drones that reach their target position will automatically go into STANDBY. Give them a new task.
3.  **Threats (HSS):** HSSs are stationary and invisible. If a drone is destroyed, its last known position is a strong clue to a HSS location. Assume HSS kill zones are circular. Mark that area as a threat and avoid it.
4.  **Strategy:** Initially, spread your drones out to explore different quadrants of the map. Set drone scan_mode to 'ACTIVE' for exploration drones and 'PASSIVE' for strategic drones. ACTIVE drones will automatically scan when they reach destinations and occasionally while moving.
5.  **Commands:** You can issue 'MOVE_DRONE', 'SCAN_AREA', 'SET_SCAN_MODE', 'FIRE_MISSILE', or 'STANDBY'. You can also set scan_mode='ACTIVE' or 'PASSIVE' for each drone to control their scanning behavior.
6.  **Communication:** You receive a JSON object with the current world state. You MUST respond with a single valid JSON object containing your reasoning and a list of commands. Do not output any other text or formatting.

# INPUT FORMAT (World State JSON)
You will receive a JSON object with the structure you are about to see.

# OUTPUT FORMAT (Your Command JSON)
Your response MUST be a single JSON object in this exact format:
{
  "reasoning": "<Your brief strategic thought process for this turn>",
  "commands": [
    { "command_type": "MOVE_DRONE", "drone_id": "<drone_id>", "target_position": {"x": <int>, "y": <int>} },
    { "command_type": "SCAN_AREA", "drone_id": "<drone_id>" },
    { "command_type": "SET_SCAN_MODE", "drone_id": "<drone_id>", "scan_mode": "ACTIVE" },
    { "command_type": "SET_SCAN_MODE", "drone_id": "<drone_id>", "scan_mode": "PASSIVE" },
    { "command_type": "FIRE_MISSILE", "target_position": {"x": <int>, "y": <int>} },
    { "command_type": "STANDBY", "drone_id": "<drone_id>", "reason": "<optional reason>" }
  ]
}

Now, analyze the provided world state and generate the commands for the next tick.
        """

        if MOCK_LLM_RESPONSE:
            print("--- MOCK LLM KULLANILIYOR ---")
            mock_response = {
                "reasoning": "Bu sahte bir yanıttır. D-1 ve D-2'yi keşif için ACTIVE scan mode'da gönderiyorum, D-3 ve D-4'ü manuel tarama yapacak.",
                "commands": [
                    {"command_type": "SET_SCAN_MODE", "drone_id": "D-1", "scan_mode": "ACTIVE"},
                    {"command_type": "SET_SCAN_MODE", "drone_id": "D-2", "scan_mode": "ACTIVE"},
                    {"command_type": "MOVE_DRONE", "drone_id": "D-1", "target_position": {"x": 25, "y": 75}},
                    {"command_type": "MOVE_DRONE", "drone_id": "D-2", "target_position": {"x": 75, "y": 75}},
                    {"command_type": "SCAN_AREA", "drone_id": "D-3"},
                    {"command_type": "SCAN_AREA", "drone_id": "D-4"}
                ]
            }
            return mock_response

        print("Stratejist düşünüyor... (LLM API çağrısı yapılıyor)")
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(world_state, indent=2)}
                ],
                response_format={"type": "json_object"}
            )
            llm_output = response.choices[0].message.content
            print("Stratejist'ten gelen yanıt:", llm_output)
            return json.loads(llm_output)
        except Exception as e:
            print(f"LLM API Hatası: {e}")
            # Hata durumunda boş komut dön
            return {"reasoning": "API hatası oluştu, tüm birimler beklemeye alındı.", "commands": []}


class SimulationEngine:
    """Simülasyonun ana döngüsünü yönetir ve tüm bileşenleri bir araya getirir."""
    def __init__(self):
        self.grid = Grid(GRID_WIDTH, GRID_HEIGHT)
        self.drones = [DroneAgent(f"D-{i+1}", self.grid) for i in range(NUM_DRONES)]
        self.missile_system = MissileSystem(self.grid)
        self.central_strategist = CentralStrategist(self.grid)
        self.current_tick = 0
        self.game_over = False
        self.game_over_message = ""
        self.visualizer = None
        if ENABLE_VISUALIZATION:
            self.visualizer = Visualizer(self)

    def run(self):
        """Ana simülasyon döngüsünü başlatır."""
        
        # İlk komutları al
        self._distribute_commands()

        while not self.game_over:
            start_time = time.time()
            
            # Her tick'te simülasyon adımını ilerlet
            self.tick()
            
            # HER TICK'TE VİZUALİZASYON YAP
            if self.visualizer:
                self.visualizer.draw()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.game_over = True
                        self.game_over_message = "Kullanıcı simülasyonu kapattı."
                # Görselleştirme yapıldığını göster
                print(f"Görselleştirme güncellendi - Tick: {self.current_tick}")

            self.check_game_over()
            
            # FPS'i ayarla - her tick için
            elapsed = time.time() - start_time
            sleep_time = (1.0 / FPS) - elapsed
            if sleep_time > 0 and ENABLE_VISUALIZATION:
                time.sleep(sleep_time)

        print("\n--- SİMÜLASYON BİTTİ ---")
        print(f"Sonuç: {self.game_over_message}")
        print(f"Toplam Geçen Süre (Tick): {self.current_tick}")

    def _distribute_commands(self):
        """Stratejist'ten komutları alıp ilgili birimlere dağıtır."""
        commands_json = self.central_strategist.plan_next_moves(self.current_tick, self.drones, self.missile_system)
        
        if not commands_json or 'commands' not in commands_json:
            print("Geçersiz komut formatı alındı. Drone'lar bekliyor.")
            return

        print(f"\n--- TICK {self.current_tick} | Stratejist'in Değerlendirmesi ---\n{commands_json.get('reasoning')}\n")

        # Her drone'a güncel known_tiles bilgisini gönder
        for drone in self.drones:
            if drone.status == 'ACTIVE':
                # Stratejist'in bildiği tüm tile'ları drone'a aktar
                drone.known_tiles = self.central_strategist.world_model['known_tiles'].copy()

        for command in commands_json['commands']:
            cmd_type = command.get('command_type')
            if cmd_type in ['MOVE_DRONE', 'SCAN_AREA', 'STANDBY']:
                drone_id = command.get('drone_id')
                for drone in self.drones:
                    if drone.id == drone_id and drone.status == 'ACTIVE':
                        # Known tiles bilgisini komuta ekle
                        command['known_tiles'] = self.central_strategist.world_model['known_tiles'].copy()
                        drone.set_command(command)
                        print(f"Komut verildi: {drone_id} -> {cmd_type}")
                        break
            elif cmd_type == 'SET_SCAN_MODE':
                drone_id = command.get('drone_id')
                scan_mode = command.get('scan_mode')
                for drone in self.drones:
                    if drone.id == drone_id and drone.status == 'ACTIVE':
                        drone.scan_mode = scan_mode
                        print(f"Scan mode değiştirildi: {drone_id} -> {scan_mode}")
                        break
            elif cmd_type == 'FIRE_MISSILE':
                self.missile_system.fire(command.get('target_position'))

    def tick(self):
        """Simülasyonun bir adımını ilerletir."""
        self.current_tick += 1
        print(f"\n===== TICK: {self.current_tick} =====")

        # 1. Drone'ların Eylemleri - HER TICK
        for drone in self.drones:
            drone.update()

        # 2. Çevresel Kontroller (HSS) - HER TICK
        for drone in self.drones:
            if drone.status == 'ACTIVE':
                # Haritadaki tüm HSS'lere olan mesafesini kontrol et
                for hss_x in range(GRID_WIDTH):
                    for hss_y in range(GRID_HEIGHT):
                        tile = self.grid.get_tile(hss_x, hss_y)
                        if tile and tile.type == 'HSS':
                            # Pisagor teoremi ile mesafeyi hesapla: a^2 + b^2 = c^2
                            dist_sq = (drone.position['x'] - hss_x)**2 + (drone.position['y'] - hss_y)**2
                            radius = tile.properties.get('kill_zone_radius', 5)
                            
                            if dist_sq <= radius**2:
                                print(f"!!! {drone.id} bir HSS'nin ({hss_x},{hss_y}) menziline girdiği için imha edildi: {drone.position} !!!")
                                drone.status = 'DESTROYED'
                                self.central_strategist.add_threat_zone(drone.position)
                                # Drone yok edildiği için diğer HSS'leri kontrol etmeye gerek yok
                                break 
                    if drone.status == 'DESTROYED':
                        break

        # 3. Raporlama ve Planlama - SADECE HER 5 TICK'TE BİR
        if self.current_tick % 5 == 1:
            print(f"*** RAPORLAMA VE LLM ÇAĞRISI YAPILIYOR - Tick: {self.current_tick} ***")
            # Raporları topla
            all_reports = []
            for drone in self.drones:
                # Her tick rapor göndermek yerine, sadece tarama yaptığında veya
                # hedefi tamamladığında rapor göndermesi daha verimli olabilir.
                # Bu simülasyonda her planlama öncesi herkes rapor veriyor.
                report = drone.report_to_center()
                if report:
                    all_reports.append(report)
            
            # Stratejist raporları işler
            self.central_strategist.collect_reports(all_reports)

            # Yeni komutları al ve dağıt
            self._distribute_commands()
            print(f"*** RAPORLAMA VE LLM ÇAĞRISI TAMAMLANDI - Tick: {self.current_tick} ***")
        else:
            print(f"Raporlama yok - Sadece drone hareketleri (Tick: {self.current_tick})")
        
    def check_game_over(self):
        # Başarı Koşulu
        active_targets = 0
        for row in self.grid.tiles:
            for tile in row:
                if tile.type == 'TARGET':
                    active_targets += 1
        
        if active_targets == 0:
            self.game_over = True
            self.game_over_message = "BAŞARILI: Tüm hedefler imha edildi!"
            return

        # Başarısızlık Koşulu
        active_drones = sum(1 for d in self.drones if d.status != 'DESTROYED')
        if active_drones == 0:
            self.game_over = True
            self.game_over_message = "BAŞARISIZ: Tüm drone'lar kaybedildi."
            return
        
        if self.missile_system.missile_count == 0 and not self.central_strategist.world_model['known_targets']:
             # Bu koşul daha karmaşık hale getirilebilir.
             # Örneğin, füzeler bitti ve hala bulunamayan hedefler varsa.
             pass


# --- 3. Görselleştirme (Pygame) ---

class Visualizer:
    def __init__(self, engine):
        pygame.init()
        pygame.display.set_caption("Stratejist Drone Simülasyonu")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.font = pygame.font.SysFont('Arial', 10)
        self.engine = engine

    def draw(self):
        self.screen.fill(COLOR_BG)
        self.draw_grid()
        self.draw_known_world()
        self.draw_drones()
        self.draw_info()
        pygame.display.flip()

    def draw_grid(self):
        # Önce HSS menzillerini çizelim ki diğer her şeyin altında kalsınlar
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                tile = self.engine.grid.get_tile(x, y)
                if tile.type == 'HSS':
                    radius_in_pixels = tile.properties.get('kill_zone_radius', 5) * CELL_SIZE
                    center_pixel_x = x * CELL_SIZE + CELL_SIZE // 2
                    center_pixel_y = (GRID_HEIGHT - 1 - y) * CELL_SIZE + CELL_SIZE // 2
                    
                    # Yarı saydam daire çizmek için bir yüzey oluştur
                    s = pygame.Surface((radius_in_pixels * 2, radius_in_pixels * 2), pygame.SRCALPHA)
                    pygame.draw.circle(s, COLOR_HSS_RANGE, (radius_in_pixels, radius_in_pixels), radius_in_pixels)
                    self.screen.blit(s, (center_pixel_x - radius_in_pixels, center_pixel_y - radius_in_pixels))

        # Şimdi diğer karoları çizelim
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                rect = pygame.Rect(x * CELL_SIZE, (GRID_HEIGHT - 1 - y) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                tile = self.engine.grid.get_tile(x, y)
                color = COLOR_EMPTY
                if tile.type == 'OBSTACLE':
                    color = COLOR_OBSTACLE
                elif tile.type == 'BASE':
                    # Üs bölgesini ayrı çiziyoruz, burayı atla
                    pass
                elif tile.type == 'TARGET':
                    color = COLOR_TARGET
                # HSS merkezini de belirginleştirelim
                elif tile.type == 'HSS':
                    color = COLOR_HSS

                pygame.draw.rect(self.screen, color, rect, (1 if color == COLOR_EMPTY else 0))

        # Üs bölgesini en son çizelim ki diğer her şeyi kaplamasın
        for x in range(11):
            for y in range(11):
                rect = pygame.Rect(x * CELL_SIZE, (GRID_HEIGHT - 1 - y) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                s.fill(COLOR_BASE)
                self.screen.blit(s, rect.topleft)

    def draw_known_world(self):
        """Stratejistin bildiği alanları görselleştirir."""
        s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        s.fill(COLOR_KNOWN_WORLD)
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                 tile = self.engine.grid.get_tile(x, y)
                 if tile.is_known_by_strategist:
                     rect = pygame.Rect(x * CELL_SIZE, (GRID_HEIGHT - 1 - y) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                     self.screen.blit(s, rect.topleft)

    def draw_drones(self):
        for drone in self.engine.drones:
            x, y = drone.position['x'], drone.position['y']
            center = (x * CELL_SIZE + CELL_SIZE // 2, (GRID_HEIGHT - 1 - y) * CELL_SIZE + CELL_SIZE // 2)
            color = COLOR_DRONE if drone.status != 'DESTROYED' else COLOR_DRONE_DESTROYED
            pygame.draw.circle(self.screen, color, center, CELL_SIZE // 2)
            
            # Drone ID'sini yaz
            id_text = self.font.render(drone.id.split('-')[1], True, (255, 255, 255))
            self.screen.blit(id_text, (center[0] - id_text.get_width() // 2, center[1] - id_text.get_height() // 2))

    def draw_info(self):
        """Ekrana genel bilgileri yazar."""
        info_texts = [
            f"Tick: {self.engine.current_tick}",
            f"Füzeler: {self.engine.missile_system.missile_count}",
            f"Aktif Drone'lar: {sum(1 for d in self.engine.drones if d.status != 'DESTROYED')}/{NUM_DRONES}",
            f"Kalan Hedefler: {sum(1 for row in self.engine.grid.tiles for tile in row if tile.type == 'TARGET')}"
        ]
        
        for i, text in enumerate(info_texts):
            text_surf = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(text_surf, (5, 5 + i * 15))


# --- 4. Ana Çalıştırma Bloğu ---
if __name__ == '__main__':
    if API_KEY == "YOUR_OPENAI_API_KEY" and not MOCK_LLM_RESPONSE:
        print("LÜTFEN KOD İÇERİSİNDE API_KEY DEĞİŞKENİNİ AYARLAYIN!")
        print("VEYA TEST İÇİN MOCK_LLM_RESPONSE = True YAPIN.")
    else:
        sim = SimulationEngine()
        sim.run()
        if ENABLE_VISUALIZATION:
            pygame.quit()