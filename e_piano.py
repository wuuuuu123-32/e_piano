import pygame
import sys
import os

# ---------- 初始化 Pygame ----------
# 调整 buffer 为 1024 减少延迟，如果听到杂音可改回 2048
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
pygame.init()

WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 500
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("e_piano - V2.0")

# 增加频道数量到 128，防止踩踏板时声音被强制切断
pygame.mixer.set_num_channels(128)

# ---------- 配置路径与映射 ----------
SAMPLE_DIR = "piano_samples" 

key_note_map = {
    # === 低音块 (C3-B3) : QWE/ASD/Z ===
    pygame.K_q: 48, pygame.K_w: 50, pygame.K_e: 52, 
    pygame.K_a: 53, pygame.K_s: 55, pygame.K_d: 57, 
    pygame.K_z: 59,

    # === 中音块 (C4-B4) : RTY/FGH/V ===
    pygame.K_r: 60, pygame.K_t: 62, pygame.K_y: 64, 
    pygame.K_f: 65, pygame.K_g: 67, pygame.K_h: 69, 
    pygame.K_v: 71,

    # === 高音块 (C5-B5) : UIO/JKL/M ===
    pygame.K_u: 72, pygame.K_i: 74, pygame.K_o: 76, 
    pygame.K_j: 77, pygame.K_k: 79, pygame.K_l: 81, 
    pygame.K_m: 83,
    
    pygame.K_COMMA: 84,

    # 黑键
    pygame.K_1: 49, pygame.K_2: 51, pygame.K_3: 54, pygame.K_4: 56, pygame.K_5: 58,
    pygame.K_6: 61, pygame.K_7: 63, pygame.K_8: 66, pygame.K_9: 68, pygame.K_0: 70,
}

# ---------- 加载采样音频 ----------
sounds = {}
for key, midi_num in key_note_map.items():
    file_name = f"{midi_num:03d}.wav"
    file_path = os.path.join(SAMPLE_DIR, file_name)
    if os.path.exists(file_path):
        sounds[key] = pygame.mixer.Sound(file_path)

active_channels = {}
# 延音踏板状态
pedal_active = False

# ---------- 绘图辅助 ----------
all_notes = sorted(list(set(key_note_map.values())))
white_notes = [n for n in range(min(all_notes), max(all_notes)+1) if (n%12) in {0,2,4,5,7,9,11}]
note_to_keys = {v: [k for k, val in key_note_map.items() if val == v] for v in all_notes}
font_key = pygame.font.Font(None, 20); font_jp = pygame.font.Font(None, 24)

def get_jp_name(n):
    mod, octv = n % 12, (n // 12) - 1
    name = {0:'1', 2:'2', 4:'3', 5:'4', 7:'5', 9:'6', 11:'7'}.get(mod, '#')
    if octv < 4: return f"-{name}"
    return f"+{name}" if octv > 4 else name

# ---------- 主循环 ----------
clock = pygame.time.Clock()
print("已开启延音踏板功能（空格键控制）")

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            
        # 1. 处理延音踏板逻辑 (按下空格)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                pedal_active = True
            
            elif event.key in sounds:
                # 如果按键已经在响，先淡出旧音，播放新音
                if event.key in active_channels:
                    active_channels[event.key].fadeout(50)
                ch = sounds[event.key].play()
                if ch: active_channels[event.key] = ch
                
        # 2. 处理按键松开 (核心延音逻辑)
        if event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE:
                pedal_active = False
                # 松开踏板时，所有“由于踏板而留着”的音符全部淡出
                # 检查当前没有被按下的键
                for k in list(active_channels.keys()):
                    if not pygame.key.get_pressed()[k]:
                        active_channels[k].fadeout(600)
                        del active_channels[k]
            
            elif event.key in active_channels:
                # 如果没踩踏板，立即淡出；如果踩了，就让它继续响
                if not pedal_active:
                    active_channels[event.key].fadeout(600)
                    del active_channels[event.key]

    # --- 绘制界面 ---
    screen.fill((30, 33, 40))
    w_width = WINDOW_WIDTH // len(white_notes)
    
    for i, n in enumerate(white_notes):
        rect = pygame.Rect(i * w_width, 100, w_width, 300)
        # 只要声道还在播放，键就显示为激活色
        is_playing = any(key_note_map[k] == n for k in active_channels)
        pygame.draw.rect(screen, (255, 230, 150) if is_playing else (230, 230, 230), rect)
        pygame.draw.rect(screen, (0, 0, 0), rect, 1)
        
        if n in note_to_keys:
            k_txt = "/".join([pygame.key.name(k).upper() for k in note_to_keys[n]])
            txt = font_key.render(k_txt, True, (80, 80, 80))
            screen.blit(txt, txt.get_rect(center=(rect.centerx, 350)))
            jp = font_jp.render(get_jp_name(n), True, (0, 0, 0))
            screen.blit(jp, jp.get_rect(center=(rect.centerx, 375)))

    # 黑键绘制
    for i, n in enumerate(white_notes[:-1]):
        if (n % 12) in {0, 2, 5, 7, 9}:
            bn = n + 1
            rect = pygame.Rect(i * w_width + w_width*0.7, 100, w_width*0.6, 180)
            is_playing = any(key_note_map[k] == bn for k in active_channels)
            pygame.draw.rect(screen, (255, 120, 0) if is_playing else (20, 20, 20), rect)

    # 显示状态信息
    pedal_color = (0, 255, 0) if pedal_active else (100, 100, 100)
    status_txt = "SUSTAIN PEDAL (SPACE)"
    txt = font_jp.render(status_txt, True, pedal_color)
    screen.blit(txt, (WINDOW_WIDTH - 250, 30))
    
    info = font_jp.render("提示：踩住[空格]演奏，音色更饱满；旋律跳跃时请注意跨区。", True, (200, 200, 200))
    screen.blit(info, (20, 20))
    
    pygame.display.flip()
    clock.tick(60)