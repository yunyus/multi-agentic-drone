#!/usr/bin/env python3
# FILE: replay_simulation.py
import pygame
import json
import sys
import time
from config import * # Renkler, FPS ve CELL_SIZE gibi ayarlar için

class ReplayEngine:
    """
    simulation_log.json dosyasını okuyarak simülasyonu görsel olarak yeniden oynatır.
    Herhangi bir oyun mantığı veya hesaplama içermez; sadece kaydedilmiş veriyi çizer.
    """
    def __init__(self, log_path):
        print("Initializing Replay Engine...")
        self.log_path = log_path
        self.log_data = self._load_log_data()
        
        # Log dosyasından temel bilgileri al
        initial_state = self.log_data['initial_state']
        grid_size = initial_state['grid_size']
        self.grid_width = grid_size['width']
        self.grid_height = grid_size['height']
        
        # Pygame'i başlat
        pygame.init()
        screen_width = self.grid_width * CELL_SIZE
        screen_height = self.grid_height * CELL_SIZE
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption(f"Replaying Simulation: {self.log_path}")
        self.font = pygame.font.SysFont('Arial', 14, bold=True)
        self.clock = pygame.time.Clock()

        # Statik harita elemanlarını yükle
        self.obstacles = initial_state.get('obstacles', [])
        self.base_bounds = initial_state.get('base_bounds', {})
        self.hss_systems = initial_state.get('hss_systems', [])
        self.initial_stationary_enemies = initial_state.get('stationary_enemies', [])
        
        # Replay sırasında durumu takip etmek için
        self.destroyed_se_ids = set() # İmha edilen sabit düşmanları takip et

    def _load_log_data(self):
        """Log dosyasını okur ve JSON verisini döndürür."""
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                print(f"Successfully loaded '{self.log_path}'.")
                return json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Log file not found at '{self.log_path}'")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"ERROR: Could not parse JSON from '{self.log_path}'. The file might be corrupted or incomplete.")
            sys.exit(1)

    def run(self):
        """Yeniden oynatma döngüsünü başlatır."""
        running = True
        paused = False
        current_tick_index = 0
        tick_data_list = self.log_data['tick_data']
        max_tick_index = len(tick_data_list) - 1

        while running:
            # Pygame olaylarını işle (kapatma, duraklatma, vb.)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        paused = not paused
                        print("Replay Paused" if paused else "Replay Resumed")
                    if event.key == pygame.K_RIGHT:
                        current_tick_index = min(current_tick_index + 1, max_tick_index)
                    if event.key == pygame.K_LEFT:
                        current_tick_index = max(current_tick_index - 1, 0)
            
            # Ekrana çizim yap
            current_tick_data = tick_data_list[current_tick_index]
            self.draw_frame(current_tick_data)
            
            # Duraklatılmadıysa bir sonraki tick'e geç
            if not paused:
                if current_tick_index < max_tick_index:
                    current_tick_index += 1
                else:
                    # Simülasyon sonuna gelindiğinde duraklat
                    if not paused:
                        paused = True
                        print("End of simulation reached. Paused.")

            # FPS'yi ayarla
            self.clock.tick(FPS)
        
        pygame.quit()
        print("Replay finished.")

    def draw_frame(self, tick_data):
        """Tek bir tick'e ait veriyi kullanarak ekranı çizer."""
        self.screen.fill(COLOR_BG)
        
        # Statik elemanları çiz
        self._draw_static_map()
        
        # O tick'teki dinamik aktörleri çiz
        self._draw_actors(tick_data)
        
        # Bilgi panelini çiz
        self._draw_info(tick_data)
        
        pygame.display.flip()

    def _draw_static_map(self):
        """Haritanın değişmeyen kısımlarını çizer: duvarlar, üs, HSS bölgeleri."""
        # Duvarlar
        for obs in self.obstacles:
            rect = pygame.Rect(obs['x'] * CELL_SIZE, (self.grid_height - 1 - obs['y']) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.screen, COLOR_OBSTACLE, rect)
            
        # Üs Bölgesi
        if self.base_bounds:
            min_x, max_x = self.base_bounds['min_x'], self.base_bounds['max_x']
            min_y, max_y = self.base_bounds['min_y'], self.base_bounds['max_y']
            base_w = (max_x - min_x + 1) * CELL_SIZE
            base_h = (max_y - min_y + 1) * CELL_SIZE
            rect = pygame.Rect(min_x * CELL_SIZE, (self.grid_height - 1 - max_y) * CELL_SIZE, base_w, base_h)
            s = pygame.Surface((base_w, base_h), pygame.SRCALPHA)
            s.fill(COLOR_BASE)
            self.screen.blit(s, rect.topleft)
            
        # HSS Menzilleri
        for hss in self.hss_systems:
            pos, radius = hss['position'], hss['radius']
            px, py = pos['x'] * CELL_SIZE + CELL_SIZE // 2, (self.grid_height - 1 - pos['y']) * CELL_SIZE + CELL_SIZE // 2
            pr = radius * CELL_SIZE
            s = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, COLOR_HSS_RANGE, (pr, pr), pr)
            self.screen.blit(s, (px - pr, py - pr))

    def _draw_actors(self, tick_data):
        """Belirli bir tick'teki drone, düşman ve füzeleri çizer."""
        # Sabit Düşmanların durumunu kontrol et
        # Bir füze hedefine ulaştıysa, o düşmanı imha edilmiş olarak işaretle
        for missile in tick_data.get('missiles', []):
            if missile['status'] == 'DETONATED':
                for se in self.initial_stationary_enemies:
                    if se['position'] == missile['target_position']:
                        self.destroyed_se_ids.add(se['id'])

        # Sabit Düşmanlar
        for se in self.initial_stationary_enemies:
            if se['id'] not in self.destroyed_se_ids:
                pos = se['position']
                rect = pygame.Rect(pos['x'] * CELL_SIZE, (self.grid_height - 1 - pos['y']) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.line(self.screen, COLOR_STATIONARY_ENEMY, (rect.left, rect.top), (rect.right, rect.bottom), 2)
                pygame.draw.line(self.screen, COLOR_STATIONARY_ENEMY, (rect.left, rect.bottom), (rect.right, rect.top), 2)

        # Dronelar
        for drone in tick_data.get('drones', []):
            pos = drone['position']
            color = COLOR_DRONE if drone['status'] != 'DESTROYED' else COLOR_DRONE_DESTROYED
            center = (pos['x'] * CELL_SIZE + CELL_SIZE // 2, (self.grid_height - 1 - pos['y']) * CELL_SIZE + CELL_SIZE // 2)
            pygame.draw.circle(self.screen, color, center, CELL_SIZE // 2)
            
        # Hareketli Düşmanlar
        for enemy in tick_data.get('moving_enemies', []):
            if enemy['status'] == 'ACTIVE':
                pos = enemy['position']
                center = (pos['x'] * CELL_SIZE + CELL_SIZE // 2, (self.grid_height - 1 - pos['y']) * CELL_SIZE + CELL_SIZE // 2)
                points = [(center[0], center[1] - CELL_SIZE // 2), (center[0] - CELL_SIZE // 2, center[1] + CELL_SIZE // 2), (center[0] + CELL_SIZE // 2, center[1] + CELL_SIZE // 2)]
                pygame.draw.polygon(self.screen, COLOR_MOVING_ENEMY, points)

        # Füzeler
        for missile in tick_data.get('missiles', []):
            pos = missile['current_position']
            center = (pos['x'] * CELL_SIZE + CELL_SIZE // 2, (self.grid_height - 1 - pos['y']) * CELL_SIZE + CELL_SIZE // 2)
            pygame.draw.circle(self.screen, COLOR_MISSILE, center, CELL_SIZE // 2 - 1)

    def _draw_info(self, tick_data):
        """Ekranın köşesine anlık bilgileri yazar."""
        tick = tick_data['tick']
        num_active_drones = sum(1 for d in tick_data.get('drones', []) if d['status'] != 'DESTROYED')
        
        info_texts = [
            f"TICK: {tick}",
            f"STATUS: {'PAUSED' if self.clock.get_fps() > 0 and tick_data == self.log_data['tick_data'][-1] else 'PLAYING'}",
            f"Active Drones: {num_active_drones}",
            "-------------------",
            "SPACE: Pause/Resume",
            "LEFT/RIGHT: Step"
        ]
        
        for i, text in enumerate(info_texts):
            text_surf = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(text_surf, (10, 10 + i * 20))

def main():
    """Betiği komut satırından çalıştırmak için ana fonksiyon."""
    if len(sys.argv) < 2:
        print("Usage: python replay_simulation.py <path_to_log_file.json>")
        sys.exit(1)
        
    log_file_path = sys.argv[1]
    
    replay_engine = ReplayEngine(log_file_path)
    replay_engine.run()

if __name__ == '__main__':
    main()