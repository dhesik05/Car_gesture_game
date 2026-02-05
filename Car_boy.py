import pygame
import cv2
import mediapipe as mp
import sys
import time
import random
import os
import math

# ================= CONFIGURATION & THEME =================
pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 1000, 480 
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("NEON DRIVE: T-REX PROTOCOL")

clock = pygame.time.Clock()

# Colors (Cyberpunk/Apocalypse Palette)
CLR_BG = (5, 5, 15)
CLR_ROAD = (25, 25, 30)
CLR_NEON_BLUE = (0, 255, 255)
CLR_NEON_PINK = (255, 0, 255)
CLR_MONSTER_RED = (255, 50, 0)
CLR_TEXT = (220, 230, 255)
CLR_ZOMBIE = (70, 100, 70)
CLR_TREX = (100, 80, 50)

# Fonts
try:
    title_font = pygame.font.SysFont("Agency FB", 60, bold=True)
    hud_font = pygame.font.SysFont("Agency FB", 28, bold=True)
    stat_font = pygame.font.SysFont("Consolas", 18)
except:
    title_font = pygame.font.SysFont("Arial", 50, bold=True)
    hud_font = pygame.font.SysFont("Arial", 24, bold=True)
    stat_font = pygame.font.SysFont("Arial", 16)

# ================= SOUND SYSTEM =================
try:
    pygame.mixer.music.load("bg_music.wav")
    pygame.mixer.music.set_volume(0.4)
    pygame.mixer.music.play(-1)
    shoot_sound = pygame.mixer.Sound("shoot.wav")
except:
    print("Sound files missing. Place bg_music.wav and shoot.wav in the same folder.")
    shoot_sound = None

# ================= PERSISTENCE =================
HIGHSCORE_FILE = "highscore_pro.txt"
high_score = 0
if os.path.exists(HIGHSCORE_FILE):
    try:
        with open(HIGHSCORE_FILE, "r") as f:
            high_score = int(f.read())
    except: high_score = 0

# ================= GAME ENGINE CLASSES =================

class ParallaxLayer:
    def __init__(self, color, speed, height_offset, pattern_type="line"):
        self.color = color
        self.speed = speed
        self.offset = 0
        self.height = height_offset
        self.pattern = pattern_type

    def update(self):
        self.offset = (self.offset - self.speed) % WIDTH

    def draw(self, surface):
        if self.pattern == "city":
            for i in range(-1, (WIDTH // 150) + 2):
                x_pos = i * 150 + self.offset
                h = 120 + (math.sin(i * 0.7) * 60)
                pygame.draw.rect(surface, self.color, (x_pos, HEIGHT - 180 - h, 100, h))
        else:
            for i in range(-1, (WIDTH // 80) + 2):
                x_pos = i * 80 + self.offset
                pygame.draw.line(surface, self.color, (x_pos, self.height), (x_pos + 40, self.height), 3)

class GameState:
    def __init__(self):
        self.reset()
        self.high_score = high_score
        self.layers = [
            ParallaxLayer((15, 15, 25), 1, 0, "city"),
            ParallaxLayer((50, 50, 60), 10, HEIGHT - 40, "line")
        ]
        
    def reset(self):
        self.score = 0
        self.bullets = []
        self.enemies = []
        self.bullet_type = 0  # 0: SMG (✌️), 1: Cannon (🤘), 2: Monster Gun (🤏)
        self.game_running = False
        self.game_over = False
        self.speed = 7
        self.ground_y = 380
        self.car_y = self.ground_y - 55
        self.last_spawn_time = 0

    def save_score(self):
        if self.score > self.high_score:
            self.high_score = self.score
            with open(HIGHSCORE_FILE, "w") as f:
                f.write(str(self.high_score))

# ================= MEDIAPIPE HANDLER =================
cap = cv2.VideoCapture(0)
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.75, min_tracking_confidence=0.7)

def get_gestures():
    success, img = cap.read()
    if not success: return None, None
    
    img = cv2.flip(img, 1)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)
    
    gesture = None
    if result.multi_hand_landmarks:
        # Draw the hand movement track lines/landmarks
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                img, 
                hand_landmarks, 
                mp_hands.HAND_CONNECTIONS,
                mp_draw.DrawingSpec(color=(0, 255, 255), thickness=2, circle_radius=2),
                mp_draw.DrawingSpec(color=(255, 0, 255), thickness=2, circle_radius=2)
            )

        lm = result.multi_hand_landmarks[0].landmark
        
        # ✊ FIST: Start
        is_fist = all(lm[t].y > lm[t-2].y for t in [8, 12, 16, 20])
        
        # ✌️ PEACE: Small Gun
        is_peace = lm[8].y < lm[6].y and lm[12].y < lm[10].y and lm[16].y > lm[14].y and lm[20].y > lm[18].y
        
        # 🤘 HORNS: Power Gun
        is_horns = lm[8].y < lm[6].y and lm[20].y < lm[18].y and lm[12].y > lm[10].y and lm[16].y > lm[14].y
        
        # 🤙 SHAKA: Restart
        is_shaka = (lm[4].x < lm[3].x - 0.05 and lm[20].y < lm[18].y and 
                    lm[8].y > lm[6].y and lm[12].y > lm[10].y and lm[16].y > lm[14].y)
        
        # 🤏 PINCH: Monster Boss Gun (Distance between thumb tip and index tip)
        dist_pinch = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
        is_pinch = dist_pinch < 0.05
        
        if is_shaka: gesture = "RESTART"
        elif is_pinch: gesture = "MONSTER_GUN"
        elif is_horns: gesture = "POWER_GUN"
        elif is_peace: gesture = "SMALL_GUN"
        elif is_fist: gesture = "START"
            
    return gesture, img

# ================= RENDER FUNCTIONS =================

def draw_car(x, y, bullet_mode):
    # Determine highlight color
    if bullet_mode == 0: color = CLR_NEON_BLUE
    elif bullet_mode == 1: color = CLR_NEON_PINK
    else: color = CLR_MONSTER_RED
    
    # Shadow
    s = pygame.Surface((110, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 100), (0, 0, 110, 20))
    screen.blit(s, (x - 10, y + 45))
    
    # Chassis
    pygame.draw.rect(screen, (30, 30, 40), (x, y + 15, 100, 30), border_radius=5)
    # Cabin
    pygame.draw.rect(screen, (50, 50, 65), (x + 15, y, 60, 25), border_top_left_radius=15, border_top_right_radius=8)
    # Window
    pygame.draw.rect(screen, (100, 200, 255, 150), (x + 45, y + 5, 25, 12), border_top_right_radius=5)
    
    # Headlights & Taillights
    pygame.draw.rect(screen, (255, 255, 200), (x + 95, y + 20, 5, 10)) 
    pygame.draw.rect(screen, (200, 0, 0), (x, y + 20, 5, 10)) 
    
    # Wheels
    for wheel_x in [x + 20, x + 80]:
        pygame.draw.circle(screen, (10, 10, 10), (int(wheel_x), y + 45), 12)
        pygame.draw.circle(screen, (50, 50, 50), (int(wheel_x), y + 45), 6)
        pygame.draw.circle(screen, color, (int(wheel_x), y + 45), 3)

def draw_enemy(e):
    if e.get("boss"): # T-REX
        # Body/Tail
        pygame.draw.ellipse(screen, CLR_TREX, (e["x"], e["y"] + 20, e["w"] - 20, e["h"] - 30))
        # Head (Large)
        pygame.draw.rect(screen, CLR_TREX, (e["x"] + 60, e["y"], 50, 40), border_radius=5)
        # Jaw
        pygame.draw.rect(screen, (80, 60, 40), (e["x"] + 60, e["y"] + 30, 45, 15), border_radius=3)
        # Eye (Glowing Red)
        pygame.draw.circle(screen, (255, 0, 0), (int(e["x"] + 95), int(e["y"] + 15)), 4)
        # Tiny Arms
        pygame.draw.rect(screen, CLR_TREX, (e["x"] + 55, e["y"] + 45, 10, 5))
        # Powerful Legs
        pygame.draw.rect(screen, (70, 50, 30), (e["x"] + 20, e["y"] + 60, 20, 40), border_radius=4)
        pygame.draw.rect(screen, (70, 50, 30), (e["x"] + 50, e["y"] + 60, 20, 40), border_radius=4)
    else: # ZOMBIE
        pygame.draw.rect(screen, CLR_ZOMBIE, (e["x"] + 5, e["y"] + 10, e["w"] - 10, e["h"] - 10), border_radius=4)
        pygame.draw.rect(screen, (90, 120, 90), (e["x"] + 10, e["y"], 20, 20), border_radius=5)
        pygame.draw.rect(screen, CLR_ZOMBIE, (e["x"] - 5, e["y"] + 15, 15, 6))
        pygame.draw.rect(screen, (255, 255, 255), (e["x"] + 15, e["y"] + 5, 4, 4))
        pygame.draw.rect(screen, (255, 255, 255), (e["x"] + 22, e["y"] + 5, 4, 4))

    # Health Bar
    pygame.draw.rect(screen, (0, 0, 0), (e["x"], e["y"] - 15, e["w"], 6))
    hp_w = int(e["w"] * (e["hp"] / e["max_hp"]))
    bar_clr = (0, 255, 0) if not e.get("boss") else CLR_MONSTER_RED
    pygame.draw.rect(screen, bar_clr, (e["x"], e["y"] - 15, hp_w, 6))

def draw_hud(state):
    hud_bg = pygame.Surface((WIDTH, 85), pygame.SRCALPHA)
    pygame.draw.rect(hud_bg, (10, 10, 20, 200), (0, 0, WIDTH, 85))
    pygame.draw.line(hud_bg, CLR_NEON_BLUE, (0, 0), (WIDTH, 0), 3)
    screen.blit(hud_bg, (0, HEIGHT - 85))

    score_lbl = hud_font.render(f"EXTERMINATIONS: {state.score}", True, CLR_TEXT)
    high_lbl = stat_font.render(f"SURVIVAL RECORD: {state.high_score}", True, (150, 150, 180))
    screen.blit(score_lbl, (40, HEIGHT - 70))
    screen.blit(high_lbl, (40, HEIGHT - 35))

    weapon_box = pygame.Surface((280, 55), pygame.SRCALPHA)
    pygame.draw.rect(weapon_box, (255, 255, 255, 30), (0, 0, 280, 55), border_radius=12)
    screen.blit(weapon_box, (WIDTH - 320, HEIGHT - 70))
    
    if state.bullet_type == 0:
        mode_str, mode_clr = "SMG (✌️)", CLR_NEON_BLUE
    elif state.bullet_type == 1:
        mode_str, mode_clr = "CANNON (🤘)", CLR_NEON_PINK
    else:
        mode_str, mode_clr = "MONSTER GUN (🤏)", CLR_MONSTER_RED
        
    mode_txt = hud_font.render(mode_str, True, mode_clr)
    screen.blit(mode_txt, (WIDTH - 300, HEIGHT - 55))

# ================= MAIN LOOP =================
def run_game():
    state = GameState()
    last_fire_time = 0
    
    while True:
        screen.fill(CLR_BG)
        
        # 1. Background
        for layer in state.layers:
            if state.game_running and not state.game_over:
                layer.update()
            layer.draw(screen)
        
        pygame.draw.rect(screen, CLR_ROAD, (0, state.ground_y, WIDTH, HEIGHT - state.ground_y))
        pygame.draw.line(screen, CLR_NEON_BLUE, (0, state.ground_y), (WIDTH, state.ground_y), 3)

        # 2. Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                state.save_score()
                pygame.quit(); sys.exit()

        # 3. Gesture Engine
        gesture, cam_img = get_gestures()
        now = time.time()

        if cam_img is not None:
            cam_img = cv2.resize(cam_img, (200, 150))
            cam_surf = pygame.surfarray.make_surface(cam_img.swapaxes(0, 1))
            pygame.draw.rect(screen, CLR_NEON_BLUE, (WIDTH - 220, 20, 204, 154), 2)
            screen.blit(cam_surf, (WIDTH - 218, 22))

        # Handle State Gestures
        if gesture == "RESTART" and state.game_over:
            state.reset()
        elif gesture == "START" and not state.game_running:
            state.reset()
            state.game_running = True
        
        # Handle Combat Gestures
        if state.game_running and not state.game_over:
            if gesture == "SMALL_GUN":
                state.bullet_type = 0
                if now - last_fire_time > 0.25:
                    state.bullets.append({"x": 180, "y": state.car_y + 20, "dmg": 1, "w": 20, "h": 6, "color": CLR_NEON_BLUE})
                    if shoot_sound: shoot_sound.play()
                    last_fire_time = now
            elif gesture == "POWER_GUN":
                state.bullet_type = 1
                if now - last_fire_time > 0.5:
                    state.bullets.append({"x": 180, "y": state.car_y + 20, "dmg": 4, "w": 30, "h": 10, "color": CLR_NEON_PINK})
                    if shoot_sound: shoot_sound.play()
                    last_fire_time = now
            elif gesture == "MONSTER_GUN":
                state.bullet_type = 2
                if now - last_fire_time > 0.8:
                    # Fires a massive beam/rocket specifically for the boss
                    state.bullets.append({"x": 180, "y": state.car_y + 10, "dmg": 10, "w": 60, "h": 20, "color": CLR_MONSTER_RED})
                    if shoot_sound: shoot_sound.play()
                    last_fire_time = now

        # 4. Logic Update
        if state.game_running and not state.game_over:
            for b in state.bullets: b["x"] += 20
            state.bullets = [b for b in state.bullets if b["x"] < WIDTH]

            for e in state.enemies: e["x"] -= state.speed
            state.enemies = [e for e in state.enemies if e["x"] > -150]

            now_ms = pygame.time.get_ticks()
            if now_ms - state.last_spawn_time > 1300:
                is_boss = (state.score > 0 and state.score % 10 == 0)
                if is_boss:
                    state.enemies.append({
                        "x": WIDTH, "y": state.ground_y - 100, "w": 140, "h": 100,
                        "hp": 40, "max_hp": 40, "color": CLR_TREX, "boss": True
                    })
                else:
                    state.enemies.append({
                        "x": WIDTH, "y": state.ground_y - 45, "w": 40, "h": 45,
                        "hp": 5, "max_hp": 5, "color": CLR_ZOMBIE, "boss": False
                    })
                state.last_spawn_time = now_ms

            player_rect = pygame.Rect(80, state.car_y, 100, 50)
            for e in state.enemies[:]:
                e_rect = pygame.Rect(e["x"], e["y"], e["w"], e["h"])
                if player_rect.colliderect(e_rect):
                    state.game_over = True
                    state.save_score()

                for b in state.bullets[:]:
                    if e_rect.colliderect(pygame.Rect(b["x"], b["y"], b["w"], b["h"])):
                        e["hp"] -= b["dmg"]
                        if b in state.bullets: state.bullets.remove(b)
                        if e["hp"] <= 0:
                            state.score += 10 if e.get("boss") else 1
                            if e in state.enemies: state.enemies.remove(e)
                            state.speed += 0.15

        # 5. Drawing
        for b in state.bullets:
            pygame.draw.rect(screen, b["color"], (b["x"], b["y"], b["w"], b["h"]), border_radius=3)
        for e in state.enemies:
            draw_enemy(e)

        draw_car(80, state.car_y, state.bullet_type)
        draw_hud(state)

        # UI Overlays
        if not state.game_running:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            t = title_font.render("T-REX PROTOCOL ACTIVE", True, CLR_NEON_BLUE)
            s = hud_font.render("HOLD ✊ TO INITIALIZE", True, CLR_TEXT)
            screen.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT//2 - 60))
            screen.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2 + 20))
            
        if state.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((80, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            t = title_font.render("TERMINATION DETECTED", True, (255, 50, 50))
            s = hud_font.render(f"SCORE: {state.score} - HOLD 🤙 TO REBOOT", True, CLR_TEXT)
            screen.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT//2 - 50))
            screen.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2 + 20))

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    try:
        run_game()
    finally:
        cap.release()
        cv2.destroyAllWindows()