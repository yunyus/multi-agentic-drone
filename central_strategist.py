# FILE: central_strategist.py
import openai
import json
import threading
import time
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
        # DRONE'LARIN SON GÖREVLERİNİ TAKİP ETMEK İÇİN YENİ BİR YAPI
        self.drone_last_command_tick = {}
        
        # Threading support for non-blocking LLM calls
        self.llm_thread = None
        self.llm_result = None
        self.llm_in_progress = False
        self.llm_lock = threading.Lock()


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
            state = {
                "id": d.id, 
                "status": d.status, 
                "battery": round(d.battery, 2), 
                "position": d.position,
                # LLM'e hangi drone'un ne kadar süredir boşta olduğunu söyleyelim
                "ticks_since_last_command": tick - self.drone_last_command_tick.get(d.id, 0)
            }
            if d.status == 'DESTROYED': state["last_known_position"] = d.position
            drones_state.append(state)

        missiles_in_flight = []
        for missile in active_missiles:
            if missile.status == 'IN_FLIGHT':
                missiles_in_flight.append({
                    "target_position": missile.target_position,
                    "current_position": missile.current_position,
                    "eta_ticks": len(missile.path) // missile.speed + (1 if len(missile.path) % missile.speed else 0)
                })

        # BİLİNEN DÜNYANIN SINIRLARINI HESAPLAYALIM
        known_x = [pos[0] for pos in self.world_model['known_tiles'].keys()]
        known_y = [pos[1] for pos in self.world_model['known_tiles'].keys()]
        map_boundaries = {
            "min_x": min(known_x) if known_x else 0,
            "max_x": max(known_x) if known_x else 0,
            "min_y": min(known_y) if known_y else 0,
            "max_y": max(known_y) if known_y else 0,
        }

        return {
            "tick": tick,
            "mission_objective": "Tüm sabit (SE) ve hareketli (ME) düşmanları yok et. SE'ler için füze, ME'ler için drone kamikaze saldırısı kullan.",
            "resources": {"missiles_left": missile_system.missile_count},
            "drones": drones_state,
            "missiles_in_flight": missiles_in_flight,
            "known_world": {
                "grid_size": self.world_model['grid_size'],
                "base_location": self.world_model['base_location'],
                "map_boundaries_explored": map_boundaries, # LLM'E YENİ BİLGİ
                "known_obstacles_count": len(known_obstacles), # Detay yerine özet verelim
                "known_stationary_enemies": known_stationary_list,
                "known_moving_enemies": known_moving_list,
                "potential_threat_zones": self.world_model['potential_threat_zones']
            }
        }

    def plan_next_moves(self, current_tick, drones, missile_system, moving_enemies, active_missiles):
        """
        Plans next moves using LLM. Uses threading to avoid blocking the main simulation loop.
        Returns immediately with cached results or None if LLM is still processing.
        """
        self.current_tick = current_tick
        
        # Check if we have a completed LLM result
        with self.llm_lock:
            if self.llm_result is not None:
                result = self.llm_result
                self.llm_result = None
                self.llm_in_progress = False
                return result
        
        # If no LLM call is in progress, start a new one
        if not self.llm_in_progress:
            world_state = self._format_state_for_llm(current_tick, drones, missile_system, moving_enemies, active_missiles)
            self._start_llm_call_async(world_state)
        
        # Return None while LLM is processing (simulation continues with existing commands)
        return None
    
    def _start_llm_call_async(self, world_state):
        """Starts an LLM call in a background thread."""
        with self.llm_lock:
            self.llm_in_progress = True
        
        # =================================================================
        # YENİ VE GÜÇLENDİRİLMİŞ SYSTEM PROMPT
        # =================================================================
        system_prompt = """
# BÖLÜM 1: ROL VE ANA HEDEF
Sen, bir drone sürüsünü yöneten "Stratejist" adlı merkezi komuta yapay zekasısın.
Ana hedefin: Tüm düşmanları en az drone kaybıyla yok etmek. Öncelikli görevin haritayı hızla açarak tüm düşmanların yerini tespit etmektir.

# BÖLÜM 2: TEMEL KOMUTLAR VE ANLAMLARI
- `MOVE_DRONE`: Bir drone'u hedefe hareket ettirir. **TEK BAŞINA TARAMA YAPMAZ.**
- `SET_SCAN_MODE`: Bir drone'un tarama modunu değiştirir. Bu, bilgi toplamanın anahtarıdır.
  - `scan_mode: 'ACTIVE'`: Drone hareket ederken periyodik olarak çevresini tarar ve raporlar. **Keşif için ZORUNLUDUR.** Pil tüketir.
  - `scan_mode: 'PASSIVE'`: Drone sadece hareket eder, tarama yapmaz. Pil tasarrufu için kullanılır.
- `FIRE_MISSILE`: Sabit hedeflere füze ateşler.
- `STANDBY`: Drone'u beklemeye alır. Üsteyken şarj olmasını sağlar.

# BÖLÜM 3: STRATEJİK PRENSİPLER (EN ÖNEMLİ BÖLÜM)

## 1. KEŞİF STRATEJİSİ: İKİ ADIMLI KOMUT
- **KURAL:** Bir drone'u keşfe göndermek için **MUTLAKA İKİ KOMUT** kullanmalısın:
  1.  `{"command_type": "SET_SCAN_MODE", "drone_id": "D-X", "scan_mode": "ACTIVE"}`
  2.  `{"command_type": "MOVE_DRONE", "drone_id": "D-X", "target_position": {"x": Y, "y": Z}}`
- **YÖNTEM: SINIRLARI ZORLA!** Boşta olan her AKTİF drone'a, **BİLİNEN DÜNYANIN SINIRINA (`map_boundaries_explored`) doğru** yeni bir keşif hedefi ver.
- **TIKANIKLIĞI ÖNLE:** Drone'ları farklı yönlere (örn: biri kuzeydoğuya, diğeri güneybatıya) göndererek yelpaze gibi açılmalarını sağla. İki drone'a çok yakın keşif hedefleri VERME.
- **SÜREKLİLİK:** Bir drone keşif hedefine ulaştığında, ona **hemen** yeni bir `MOVE_DRONE` hedefi ver. Zaten 'ACTIVE' modda olduğu için tekrar `SET_SCAN_MODE` demene gerek yok.

## 2. KAYNAK YÖNETİMİ
- **Pil Yönetimi:** Pili %25'in altına düşen drone'u üsse (`x:5, y:5` civarı) geri çağırmak için `MOVE_DRONE` komutu ver. Pil tasarrufu için üsse dönerken `SET_SCAN_MODE` ile modunu `'PASSIVE'` yapabilirsin. Üsteki drone'lara `STANDBY` komutu ver.
- **Füze Disiplini:** Sadece `known_stationary_enemies` listesindeki hedeflere ateş et. `missiles_in_flight` listesini kontrol et.

## 3. ZORLU HEDEFLER
- Eğer bir drone hedefine yol bulamadığını raporlarsa (görevini iptal ederse), bu hedefin etrafı kapalı olabilir. O drone'a veya yakındaki başka bir drone'a, hedefin etrafındaki bilinmeyen bölgeleri keşfetmesi için yeni `MOVE_DRONE` görevleri ver. Amaç, hedefe yeni bir geçit bulmaktır.

# BÖLÜM 4: ÖRNEK KOMUT AKIŞI
"reasoning": "D-1 ve D-2'yi keşfe gönderiyorum. D-1'i kuzeye, D-2'yi doğuya yönlendiriyorum. Tarama modlarını ACTIVE yapıyorum. D-7'nin pili az, üsse dönüyor."
"commands": [
  {"command_type": "SET_SCAN_MODE", "drone_id": "D-1", "scan_mode": "ACTIVE"},
  {"command_type": "MOVE_DRONE", "drone_id": "D-1", "target_position": {"x": 25, "y": 45}},
  {"command_type": "SET_SCAN_MODE", "drone_id": "D-2", "scan_mode": "ACTIVE"},
  {"command_type": "MOVE_DRONE", "drone_id": "D-2", "target_position": {"x": 45, "y": 25}},
  {"command_type": "SET_SCAN_MODE", "drone_id": "D-7", "scan_mode": "PASSIVE"},
  {"command_type": "MOVE_DRONE", "drone_id": "D-7", "target_position": {"x": 5, "y": 5}}
]

# BÖLÜM 5: ÇIKTI FORMATI
- Cevabın TEK BİR GEÇERLİ JSON objesi olmalıdır. Her aktif ve görevi olmayan drone için komut oluştur.
"""

        # Start the LLM call in a background thread
        self.llm_thread = threading.Thread(target=self._llm_worker_thread, args=(system_prompt, world_state))
        self.llm_thread.daemon = True
        self.llm_thread.start()
    
    def _llm_worker_thread(self, system_prompt, world_state):
        """Worker thread that makes the LLM API call."""
        try:
            # Make the LLM call
            if not MOCK_LLM_RESPONSE:
                response_json = self._get_llm_response(system_prompt, world_state)
            else:
                response_json = {"reasoning": "Mock: Sending D-1 to explore NE, D-2 to explore SW.",
                                 "commands": [
                                     {"command_type": "MOVE_DRONE", "drone_id": "D-1", "target_position": {"x": 45, "y": 45}},
                                     {"command_type": "MOVE_DRONE", "drone_id": "D-2", "target_position": {"x": 5, "y": 35}}
                                 ]}
            
            # Update command tick tracking
            if response_json and 'commands' in response_json:
                for cmd in response_json['commands']:
                    if 'drone_id' in cmd:
                        self.drone_last_command_tick[cmd['drone_id']] = self.current_tick
            
            # Store the result safely
            with self.llm_lock:
                self.llm_result = response_json
                
        except Exception as e:
            print(f"LLM Worker Thread Error: {e}")
            # Store error result
            with self.llm_lock:
                self.llm_result = {"reasoning": "API error occurred, all units on standby.", "commands": []}

    def _get_llm_response(self, system_prompt, world_state):
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