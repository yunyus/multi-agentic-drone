# FILE: central_strategist.py
import openai
import json
from config import *

class CentralStrategist:
    """Collects information, makes plans with GPT-4o and sends commands."""
    def __init__(self, grid):
        self.llm_api_key = API_KEY
        self.llm_model = LLM_MODEL
        self.client = openai.OpenAI(api_key=self.llm_api_key)
        self.grid = grid
        self.world_model = {
            "grid_size": {"width": GRID_WIDTH, "height": GRID_HEIGHT},
            "base_location": {"x_range": [0, 10], "y_range": [0, 10]},
            "known_tiles": {},
            "known_stationary_enemies": {},
            "known_moving_enemies": {},
            "potential_threat_zones": []
        }
        self.current_tick = 0

    def collect_reports(self, reports, current_tick):
        """Receives drone reports and updates world model."""
        self.current_tick = current_tick
        for report in reports:
            if not report: continue
            
            # Process tile scan results
            for tile_data in report['scan_results']:
                x, y = tile_data['position']['x'], tile_data['position']['y']
                self.world_model['known_tiles'][(x,y)] = tile_data
                self.grid.get_tile(x, y).is_known_by_strategist = True

                if tile_data['type'] == 'STATIONARY_ENEMY':
                    enemy_id = tile_data['properties']['enemy_id']
                    if enemy_id not in self.world_model['known_stationary_enemies']:
                        print(f"STRATEGIST: New stationary enemy {enemy_id} found at ({x},{y})")
                        self.world_model['known_stationary_enemies'][enemy_id] = {
                            "position": tile_data['position'], "status": "CONFIRMED"
                        }
            
            # Process spotted moving enemies
            for enemy_data in report.get('spotted_enemies', []):
                enemy_id = enemy_data['id']
                if enemy_id not in self.world_model['known_moving_enemies']:
                     print(f"STRATEGIST: New moving enemy {enemy_id} spotted at {enemy_data['position']}")
                self.world_model['known_moving_enemies'][enemy_id] = {
                    "position": enemy_data['position'],
                    "last_seen_tick": self.current_tick
                }

    def add_threat_zone(self, drone_position):
        """Identifies HSS location and radius when a drone is destroyed."""
        # This logic remains the same as it correctly identifies HSS threats
        for x in range(self.grid.width):
            for y in range(self.grid.height):
                tile = self.grid.get_tile(x, y)
                if tile and tile.type == 'HSS':
                    dist_sq = (drone_position['x'] - x)**2 + (drone_position['y'] - y)**2
                    hss_radius = tile.properties.get('kill_zone_radius', 5)
                    if dist_sq <= hss_radius**2:
                        is_known = any(z.get('hss_location') == {'x': x, 'y': y} for z in self.world_model['potential_threat_zones'])
                        if not is_known:
                            self.world_model['potential_threat_zones'].append({
                                "hss_location": {"x": x, "y": y}, "radius": hss_radius, "confidence": "CONFIRMED"
                            })
                            print(f"STRATEGIST: HSS DISCOVERED! Location: ({x},{y}), Radius: {hss_radius}")
                        return
        print(f"STRATEGIST: Warning - Drone lost but no HSS found at {drone_position}")

    def _format_state_for_llm(self, tick, drones, missile_system, moving_enemies, active_missiles):
        """Converts current world model to JSON for the LLM."""
        known_obstacles = [{'x': x, 'y': y} for (x,y), tile in self.world_model['known_tiles'].items() if tile['type'] == 'OBSTACLE']
        known_stationary_list = [{"id": eid, **edata} for eid, edata in self.world_model['known_stationary_enemies'].items()]
        known_moving_list = [{"id": eid, **edata} for eid, edata in self.world_model['known_moving_enemies'].items()]
        
        drones_state = []
        for d in drones:
            state = {"id": d.id, "status": d.status, "battery": round(d.battery, 2), "position": d.position}
            if d.status == 'DESTROYED': state["last_known_position"] = d.position
            drones_state.append(state)

        # Add information about missiles currently in flight
        missiles_in_flight = []
        for missile in active_missiles:
            if missile.status == 'IN_FLIGHT':
                missiles_in_flight.append({
                    "target_position": missile.target_position,
                    "current_position": missile.current_position,
                    "eta_ticks": len(missile.path) // missile.speed + (1 if len(missile.path) % missile.speed else 0)
                })

        return {
            "tick": tick,
            "mission_objective": "Destroy all stationary (SE) and moving (ME) enemies. Use missiles for SE, and drone kamikaze attacks for ME.",
            "resources": {"missiles_left": missile_system.missile_count},
            "drones": drones_state,
            "missiles_in_flight": missiles_in_flight,
            "known_world": {
                "grid_size": self.world_model['grid_size'],
                "base_location": self.world_model['base_location'],
                "known_obstacles": known_obstacles,
                "known_stationary_enemies": known_stationary_list,
                "known_moving_enemies": known_moving_list,
                "potential_threat_zones": self.world_model['potential_threat_zones']
            }
        }

    def plan_next_moves(self, current_tick, drones, missile_system, moving_enemies, active_missiles):
        """Sends request to LLM and parses returned commands."""
        world_state = self._format_state_for_llm(current_tick, drones, missile_system, moving_enemies, active_missiles)
        
        system_prompt = """
# ROLE AND GOAL
You are "Stratejist", a central command AI for a drone swarm. Your mission is to destroy all enemies.

# ENEMY TYPES & RULES OF ENGAGEMENT
1.  **Stationary Enemies (SE):** Fixed targets. Destroy ONLY with `FIRE_MISSILE`.
2.  **Moving Enemies (ME):** Mobile targets. Destroy ONLY by sending a drone to their exact location for a kamikaze attack (`MOVE_DRONE`). When a drone and ME are on the same tile, they are both destroyed automatically.

# STRATEGY & RULES
1.  **Missile Attacks:** Use `FIRE_MISSILE` on `known_stationary_enemies`. Missiles use safe paths based on known tiles.
2.  **Kamikaze Attacks:** Use `MOVE_DRONE` to hunt `known_moving_enemies`. Since they move, their position data can be stale. You might need to send drones to their last known position to find them again.
3.  **Exploration:** Spread drones out to explore the map and find all enemies. Use `scan_mode: 'ACTIVE'` for explorers.
4.  **Resource Management:** Drones have limited battery and must return to base (0,0 to 10,10) to recharge.
5.  **Threat Avoidance:** Avoid `potential_threat_zones` (HSS kill zones).
6.  **CRITICAL - NO DUPLICATE MISSILES:** Check `missiles_in_flight` before firing. NEVER fire at coordinates that already have a missile heading toward them! Each missile is precious.
7.  **Response Format:** You MUST respond with a single valid JSON object.

# OUTPUT FORMAT
{
  "reasoning": "<Your brief strategic thought process>",
  "commands": [
    {"command_type": "MOVE_DRONE", "drone_id": "D-1", "target_position": {"x": 55, "y": 60}},
    {"command_type": "FIRE_MISSILE", "target_position": {"x": 80, "y": 20}},
    {"command_type": "SCAN_AREA", "drone_id": "D-3"},
    {"command_type": "SET_SCAN_MODE", "drone_id": "D-4", "scan_mode": "ACTIVE"},
    {"command_type": "STANDBY", "drone_id": "D-5"}
  ]
}

Analyze the world state and generate commands.
        """

        if MOCK_LLM_RESPONSE:
            return {"reasoning": "Mock: Sending D-1 to explore, D-2 to hunt a moving enemy.",
                    "commands": [
                        {"command_type": "MOVE_DRONE", "drone_id": "D-1", "target_position": {"x": 75, "y": 75}},
                        {"command_type": "MOVE_DRONE", "drone_id": "D-2", "target_position": {"x": 75, "y": 25}}
                    ]}

        print("Strategist thinking... (Making LLM API call)")
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
            print("Response from Strategist:", llm_output)
            return json.loads(llm_output)
        except Exception as e:
            print(f"LLM API Error: {e}")
            return {"reasoning": "API error occurred, all units on standby.", "commands": []}