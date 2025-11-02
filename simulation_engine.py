# FILE: simulation_engine.py
import time
from config import *
from grid import Grid
from drone_agent import DroneAgent
from missile_system import MissileSystem
from central_strategist import CentralStrategist
from visualizer import Visualizer
from enemy import MovingEnemy
from simulation_logger import SimulationLogger

if ENABLE_VISUALIZATION:
    import pygame

class SimulationEngine:
    """Manages the main simulation loop and all interacting components."""
    def __init__(self):
        # ... (init metodunun geri kalanı aynı kalacak) ...
        self.grid = Grid(GRID_WIDTH, GRID_HEIGHT)
        self.drones = [DroneAgent(f"D-{i+1}", self.grid) for i in range(NUM_DRONES)]
        self.missile_system = MissileSystem(self.grid)
        self.central_strategist = CentralStrategist(self.grid)
        self.moving_enemies = [MovingEnemy(f"ME-{i+1}", self.grid) for i in range(NUM_MOVING_ENEMIES)]
        self.active_missiles = []
        self.current_tick = 0
        self.game_over = False
        self.game_over_message = ""
        self.logger = SimulationLogger()
        self.visualizer = None
        if ENABLE_VISUALIZATION:
            self.visualizer = Visualizer(self)

    def run(self):
        """Starts the main simulation loop."""
        self.logger.log_initial_state(self.grid)
        self.logger.log_tick_state(0, self.drones, self.moving_enemies, self.active_missiles)
        self._distribute_commands()
        
        try:
            while not self.game_over:
                start_time = time.time()
                self.tick()
                if self.visualizer:
                    self.visualizer.draw()
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            self.game_over = True
                self.check_game_over()
                elapsed = time.time() - start_time
                sleep_time = (1.0 / FPS) - elapsed
                if sleep_time > 0 and ENABLE_VISUALIZATION: time.sleep(sleep_time)
        finally:
            print(f"\n--- SIMULATION ENDED: {self.game_over_message} ---")


    def tick(self):
        """Advances the simulation by one step."""
        self.current_tick += 1
        print(f"\n===== TICK: {self.current_tick} =====")

        # 1. Düşmanlar hareket eder
        for enemy in self.moving_enemies: enemy.update(self.current_tick)
        
        # DEĞİŞTİRİLDİ: Füze güncelleme mantığı yeni bir metoda taşındı
        self._update_missiles_and_threats()

        # 3. Dronelar hareket eder ve görevlerini yapar
        for drone in self.drones: drone.update(self.current_tick)
        
        # 4. Anlık avlanma ve çarpışma kontrolleri
        self.check_and_initiate_hunts()
        self.check_kamikaze_attacks()
        self.check_hss_threats()       # Bu metot drone'ları kontrol eder, füzeleri değil
        
        if self.current_tick % LLM_CALL_FREQUENCY == 1:
            reports = [d.report_to_center(self.moving_enemies) for d in self.drones]
            self.central_strategist.collect_reports(reports, self.current_tick)
            self._distribute_commands()

        self.logger.log_tick_state(self.current_tick, self.drones, self.moving_enemies, self.active_missiles)

    # YENİ: Füze hareketini ve HSS tehdidini yöneten özel metot
    def _update_missiles_and_threats(self):
        """
        Updates all active missiles. Moves them, checks for HSS interceptions,
        and handles target impacts.
        """
        all_hss_tiles = [tile for row in self.grid.tiles for tile in row if tile.type == 'HSS']

        for missile in self.active_missiles[:]:
            missile.update()

            # Füze hala havadayken HSS tarafından vurulup vurulmadığını kontrol et
            if missile.status == 'IN_FLIGHT':
                for hss_tile in all_hss_tiles:
                    hss_pos = {'x': hss_tile.x, 'y': hss_tile.y}
                    radius_sq = hss_tile.properties['kill_zone_radius'] ** 2
                    dist_sq = (missile.current_position['x'] - hss_pos['x'])**2 + (missile.current_position['y'] - hss_pos['y'])**2
                    
                    if dist_sq <= radius_sq:
                        print(f"!!! MISSILE INTERCEPTED! Missile flying to {missile.target_position} was destroyed by HSS at {hss_pos} !!!")
                        missile.status = 'DETONATED' # Füzenin durumunu patladı olarak ayarla
                        break # Füze imha oldu, diğer HSS'leri kontrol etmeye gerek yok
            
            # Füzenin durumu 'DETONATED' ise (hedefe ulaştığı veya vurulduğu için)
            if missile.status == 'DETONATED':
                # Sadece hedefine başarıyla ulaşmışsa hasar ver
                is_at_target = missile.current_position == missile.target_position
                
                # Füzenin yolu bittiğinde de hedefe ulaşmış sayılır (hız > 1 durumları için)
                is_path_empty = not missile.path 

                if is_at_target or is_path_empty:
                    # Eğer konumu hedefe eşitse, bu HSS tarafından vurulmadığı anlamına gelir.
                    # HSS tarafından vurulsaydı, konumu hedefle eşleşmezdi.
                    if missile.current_position == missile.target_position:
                         self.handle_missile_impact(missile)

                # Her iki durumda da (hedefe varma veya imha edilme) füzeyi listeden kaldır
                self.active_missiles.remove(missile)

    # ... (kodun geri kalanı aynı kalacak) ...
    def check_and_initiate_hunts(self):
        """Checks if any drone spots a moving enemy and initiates a hunt."""
        active_enemies = [e for e in self.moving_enemies if e.status == 'ACTIVE']
        for drone in self.drones:
            if drone.status != 'ACTIVE': continue
            
            if not drone.current_command.get('is_hunting'):
                for enemy in active_enemies:
                    dist_sq = (drone.position['x'] - enemy.position['x'])**2 + (drone.position['y'] - enemy.position['y'])**2
                    if dist_sq <= DRONE_SCAN_RADIUS**2:
                        print(f"!!! {drone.id} SPOTTED {enemy.id}! Overriding mission to HUNT! !!!")
                        hunt_command = {
                            "command_type": "MOVE_DRONE",
                            "target_position": enemy.position.copy(),
                            "is_hunting": True
                        }
                        drone.set_command(hunt_command)
                        break

            elif drone.current_command.get('is_hunting'):
                hunted_enemy = next((e for e in active_enemies if drone.target_position == e.position), None)
                if not hunted_enemy:
                    closest_enemy = None
                    min_dist_sq = float('inf')
                    for enemy in active_enemies:
                        dist_sq = (drone.position['x'] - enemy.position['x'])**2 + (drone.position['y'] - enemy.position['y'])**2
                        if dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            closest_enemy = enemy
                    
                    if closest_enemy:
                        drone.target_position = closest_enemy.position.copy()
                        drone.path = []

    def _distribute_commands(self):
        commands_json = self.central_strategist.plan_next_moves(
            self.current_tick, self.drones, self.missile_system, self.moving_enemies, self.active_missiles
        )
        # If LLM is still processing, commands_json will be None - that's OK, simulation continues
        if not commands_json or 'commands' not in commands_json: 
            if commands_json is None:
                print(f"\n--- TICK {self.current_tick} | Strategist is thinking... (LLM processing) ---")
            return
        print(f"\n--- TICK {self.current_tick} | Strategist Reasoning ---\n{commands_json.get('reasoning')}\n")

        threat_zones = self.central_strategist.world_model['potential_threat_zones']
        known_tiles = self.central_strategist.world_model['known_tiles']

        for command in commands_json['commands']:
            cmd_type = command.get('command_type')
            drone_id = command.get('drone_id')
            if cmd_type in ['MOVE_DRONE', 'SCAN_AREA', 'STANDBY', 'SET_SCAN_MODE']:
                for drone in self.drones:
                    if drone.id == drone_id and drone.status == 'ACTIVE':
                        enhanced_command = command.copy()
                        enhanced_command['threat_zones'] = threat_zones
                        enhanced_command['known_tiles'] = known_tiles
                        drone.set_command(enhanced_command)
                        break
                        
            elif cmd_type == 'FIRE_MISSILE':
                target_pos = command.get('target_position')
                if not target_pos: continue
                
                is_target_already_locked = False
                for missile in self.active_missiles:
                    if missile.target_position['x'] == target_pos['x'] and missile.target_position['y'] == target_pos['y']:
                        is_target_already_locked = True
                        print(f"ENGINE: Missile launch to {target_pos} aborted. A missile is already in flight to this target.")
                        break
                
                if not is_target_already_locked:
                    missile = self.missile_system.fire(target_pos, self.central_strategist.world_model['known_tiles'])
                    if missile: self.active_missiles.append(missile)

    def handle_missile_impact(self, missile):
        x, y = missile.target_position['x'], missile.target_position['y']
        tile = self.grid.get_tile(x, y)
        if tile and tile.type == 'STATIONARY_ENEMY':
            enemy_id = tile.properties['enemy_id']
            print(f"IMPACT! Missile destroyed {enemy_id} at ({x}, {y})!")
            tile.type = 'EMPTY'
            if enemy_id in self.central_strategist.world_model['known_stationary_enemies']:
                del self.central_strategist.world_model['known_stationary_enemies'][enemy_id]
        else:
            print(f"IMPACT! Missile detonated at ({x}, {y}) but hit nothing.")

    def check_kamikaze_attacks(self):
        for drone in self.drones:
            if drone.status != 'ACTIVE': continue
            for enemy in self.moving_enemies:
                if enemy.status != 'ACTIVE': continue
                if drone.position == enemy.position:
                    print(f"!!! KAMIKAZE ATTACK! {drone.id} destroyed {enemy.id} at {drone.position} !!!")
                    drone.status = 'DESTROYED'
                    enemy.status = 'DESTROYED'
                    if enemy.id in self.central_strategist.world_model['known_moving_enemies']:
                        del self.central_strategist.world_model['known_moving_enemies'][enemy.id]

    def check_hss_threats(self):
        for drone in self.drones:
            if drone.status == 'ACTIVE':
                for x in range(self.grid.width):
                    for y in range(self.grid.height):
                        hss_tile = self.grid.get_tile(x, y)
                        if hss_tile and hss_tile.type == 'HSS':
                            dist_sq = (drone.position['x'] - x)**2 + (drone.position['y'] - y)**2
                            if dist_sq <= hss_tile.properties['kill_zone_radius']**2:
                                print(f"!!! {drone.id} destroyed by HSS at ({x},{y}) !!!")
                                drone.status = 'DESTROYED'
                                self.central_strategist.add_threat_zone(drone.position)
                                break
                    if drone.status == 'DESTROYED': break

    def check_game_over(self):
        active_stationary = sum(1 for r in self.grid.tiles for t in r if t.type == 'STATIONARY_ENEMY')
        active_moving = sum(1 for e in self.moving_enemies if e.status == 'ACTIVE')
        if active_stationary == 0 and active_moving == 0:
            self.game_over = True
            self.game_over_message = "SUCCESS: All enemies destroyed!"
            return

        active_drones = sum(1 for d in self.drones if d.status != 'DESTROYED')
        if active_drones == 0:
            self.game_over = True
            self.game_over_message = "FAILURE: All drones lost."