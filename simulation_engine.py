# FILE: simulation_engine.py
import time
from config import *
from grid import Grid
from drone_agent import DroneAgent
from missile_system import MissileSystem
from central_strategist import CentralStrategist
from visualizer import Visualizer
from enemy import MovingEnemy

if ENABLE_VISUALIZATION:
    import pygame

class SimulationEngine:
    """Manages the main simulation loop and all interacting components."""
    def __init__(self):
        self.grid = Grid(GRID_WIDTH, GRID_HEIGHT)
        self.drones = [DroneAgent(f"D-{i+1}", self.grid) for i in range(NUM_DRONES)]
        self.missile_system = MissileSystem(self.grid)
        self.central_strategist = CentralStrategist(self.grid)
        self.moving_enemies = [MovingEnemy(f"ME-{i+1}", self.grid) for i in range(NUM_MOVING_ENEMIES)]
        self.active_missiles = []
        self.current_tick = 0
        self.game_over = False
        self.game_over_message = ""
        self.visualizer = None
        if ENABLE_VISUALIZATION:
            self.visualizer = Visualizer(self)

    def run(self):
        """Starts the main simulation loop."""
        self._distribute_commands()
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
        print(f"\n--- SIMULATION ENDED: {self.game_over_message} ---")

    def tick(self):
        """Advances the simulation by one step."""
        self.current_tick += 1
        print(f"\n===== TICK: {self.current_tick} =====")

        # 1. Düşmanlar hareket eder
        for enemy in self.moving_enemies: enemy.update(self.current_tick)
        
        # 2. Füzeler hareket eder
        for missile in self.active_missiles[:]:
            missile.update()
            if missile.status == 'DETONATED':
                self.handle_missile_impact(missile)
                self.active_missiles.remove(missile)

        # 3. Dronelar hareket eder ve görevlerini yapar
        for drone in self.drones: drone.update(self.current_tick)
        
        # 4. YENİ: Anlık avlanma ve çarpışma kontrolleri
        self.check_and_initiate_hunts() # Düşman gören drone'lar av moduna geçer
        self.check_kamikaze_attacks()  # Av başarıya ulaştı mı?
        self.check_hss_threats()       # Drone HSS tarafından vuruldu mu?
        
        if self.current_tick % LLM_CALL_FREQUENCY == 1:
            reports = [d.report_to_center(self.moving_enemies) for d in self.drones]
            self.central_strategist.collect_reports(reports, self.current_tick)
            self._distribute_commands()

    def check_and_initiate_hunts(self):
        """Checks if any drone spots a moving enemy and initiates a hunt."""
        active_enemies = [e for e in self.moving_enemies if e.status == 'ACTIVE']
        for drone in self.drones:
            if drone.status != 'ACTIVE': continue
            
            # Drone zaten bir ME avlamıyorsa...
            if not drone.current_command.get('is_hunting'):
                for enemy in active_enemies:
                    dist_sq = (drone.position['x'] - enemy.position['x'])**2 + (drone.position['y'] - enemy.position['y'])**2
                    # Eğer drone düşmanı tarama menzilinde gördüyse...
                    if dist_sq <= DRONE_SCAN_RADIUS**2:
                        print(f"!!! {drone.id} SPOTTED {enemy.id}! Overriding mission to HUNT! !!!")
                        # LLM görevini ez ve yeni av görevini ver!
                        hunt_command = {
                            "command_type": "MOVE_DRONE",
                            "target_position": enemy.position.copy(), # Düşmanın o anki konumunu hedefle
                            "is_hunting": True # Bu bir av görevi
                        }
                        drone.set_command(hunt_command)
                        break # Bu drone için av bulundu, diğer düşmanlara bakma

            # Eğer drone zaten avlanıyorsa, hedefini güncel tut
            elif drone.current_command.get('is_hunting'):
                # Avladığı düşmanı bul
                hunted_enemy = next((e for e in active_enemies if drone.target_position == e.position), None)
                if not hunted_enemy: # Eğer düşman öldüyse veya menzilden çıktıysa yeni bir hedef bulalım
                    # En yakındaki düşmanı hedefle
                    closest_enemy = None
                    min_dist_sq = float('inf')
                    for enemy in active_enemies:
                        dist_sq = (drone.position['x'] - enemy.position['x'])**2 + (drone.position['y'] - enemy.position['y'])**2
                        if dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            closest_enemy = enemy
                    
                    if closest_enemy:
                         # Hedefi güncelle
                        drone.target_position = closest_enemy.position.copy()
                        drone.path = [] # Yeni bir yol hesaplaması için yolu temizle

    def _distribute_commands(self):
        commands_json = self.central_strategist.plan_next_moves(
            self.current_tick, self.drones, self.missile_system, self.moving_enemies, self.active_missiles
        )
        if not commands_json or 'commands' not in commands_json: return
        print(f"\n--- TICK {self.current_tick} | Strategist Reasoning ---\n{commands_json.get('reasoning')}\n")

        # Get current threat zones and known tiles from strategist
        threat_zones = self.central_strategist.world_model['potential_threat_zones']
        known_tiles = self.central_strategist.world_model['known_tiles']

        for command in commands_json['commands']:
            cmd_type = command.get('command_type')
            drone_id = command.get('drone_id')
            if cmd_type in ['MOVE_DRONE', 'SCAN_AREA', 'STANDBY', 'SET_SCAN_MODE']:
                for drone in self.drones:
                    if drone.id == drone_id and drone.status == 'ACTIVE':
                        # Add threat zones and known tiles to every drone command
                        enhanced_command = command.copy()
                        enhanced_command['threat_zones'] = threat_zones
                        enhanced_command['known_tiles'] = known_tiles
                        drone.set_command(enhanced_command)
                        break
                        
            elif cmd_type == 'FIRE_MISSILE':
                target_pos = command.get('target_position')
                if not target_pos: continue
                
                # YENİ: Duplicate füze atışını engelleme
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
                tile = self.grid.get_tile(drone.position['x'], drone.position['y'])
                # Check for actual HSS tiles, not just known zones
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