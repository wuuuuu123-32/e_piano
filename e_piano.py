import pygame
import numpy as np
import sys

# ---------- 初始化 Pygame ----------
# 【优化】：将 buffer 从 512 提升到 2048，解决快速点按时的“滋滋”电流声
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
pygame.init()

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 500
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("e_piano - 多八度 + 真实声学衰减")

pygame.mixer.set_num_channels(64) # 增加通道数，防止快速弹奏时吞音

# ---------- 声音合成参数 ----------
SAMPLE_RATE = 44100
# 【优化】：延长采样时间，不使用循环，模拟琴弦完全静止的自然过程
DURATION = 8.0  

def midi_to_freq(note):
    return 440 * (2 ** ((note - 69) / 12))

def generate_piano_like_wave(freq, duration=DURATION):
    frames = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, frames, endpoint=False)
    wave = np.zeros(frames)

    pitch_ratio = np.clip(freq / 261.63, 0.5, 4.0)
    
    # 模拟三根琴弦
    detune_cents = 1.0
    freqs = [freq, freq * (2 ** (detune_cents/1200)), freq * (2 ** (-detune_cents/1200))]
    inharmonic = 0.00015

    for f_base in freqs:
        max_harmonics = int(max(3, 15 - (freq / 200)))
        max_harmonics = min(max_harmonics, 15)
        for n in range(1, max_harmonics + 1):
            f_n = f_base * n * np.sqrt(1 + inharmonic * (n ** 2))
            if f_n > SAMPLE_RATE / 2:
                continue
            amplitude = 1.0 / (n ** (1.5 + 0.3 * pitch_ratio))
            
            # 【核心优化】：泛音自然衰减，高频衰减极快，低频绵长
            harmonic_decay = (1.0 + n * 0.7) * (1.2 * pitch_ratio)
            harmonic_env = np.exp(-t * harmonic_decay)
            wave += amplitude * harmonic_env * np.sin(2 * np.pi * f_n * t)

    # 琴槌敲击噪声
    attack_noise_len = int(max(0.005, 0.03 / pitch_ratio) * SAMPLE_RATE)
    if attack_noise_len > 0:
        noise_amp = 0.2 / pitch_ratio
        noise = np.random.normal(0, noise_amp, attack_noise_len)
        noise_envelope = np.exp(-np.linspace(0, 8, attack_noise_len))
        wave[:attack_noise_len] += noise * noise_envelope

    wave = wave / np.max(np.abs(wave))

    # 【核心优化】：真实的钢琴主包络（没有平稳的Sustain，只有持续衰减）
    master_envelope = np.exp(-t * (0.8 * pitch_ratio)) 
    
    # 极短的起音防止开头爆音
    attack_len = int(0.005 * SAMPLE_RATE)
    master_envelope[:attack_len] = np.linspace(0, 1, attack_len)

    wave *= master_envelope

    wave = (wave * 32767).astype(np.int16)
    stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
    return pygame.sndarray.make_sound(stereo)

# ---------- 全新多八度键盘映射 ----------
key_note_map = {
    # === 低音区 (C3 - B3) ===
    pygame.K_z: 48,  # C3 (白)
    pygame.K_s: 49,  # C#3 (黑)
    pygame.K_x: 50,  # D3 (白)
    pygame.K_d: 51,  # D#3 (黑)
    pygame.K_c: 52,  # E3 (白)
    pygame.K_v: 53,  # F3 (白)
    pygame.K_g: 54,  # F#3 (黑)
    pygame.K_b: 55,  # G3 (白)
    pygame.K_h: 56,  # G#3 (黑)
    pygame.K_n: 57,  # A3 (白)
    pygame.K_j: 58,  # A#3 (黑)
    pygame.K_m: 59,  # B3 (白)

    # === 中音区 (C4 - B4) ===
    pygame.K_q: 60,  # C4 (白 - 中央C)
    pygame.K_2: 61,  # C#4 (黑)
    pygame.K_w: 62,  # D4 (白)
    pygame.K_3: 63,  # D#4 (黑)
    pygame.K_e: 64,  # E4 (白)
    pygame.K_r: 65,  # F4 (白)
    pygame.K_5: 66,  # F#4 (黑)
    pygame.K_t: 67,  # G4 (白)
    pygame.K_6: 68,  # G#4 (黑)
    pygame.K_y: 69,  # A4 (白)
    pygame.K_7: 70,  # A#4 (黑)
    pygame.K_u: 71,  # B4 (白)

    # === 高音区延伸 (C5 - G5) ===
    pygame.K_i: 72,  # C5 (白)
    pygame.K_9: 73,  # C#5 (黑)
    pygame.K_o: 74,  # D5 (白)
    pygame.K_0: 75,  # D#5 (黑)
    pygame.K_p: 76,  # E5 (白)
    pygame.K_LEFTBRACKET: 77, # F5 (白, '[' 键)
    pygame.K_EQUALS: 78,      # F#5 (黑, '=' 键)
    pygame.K_RIGHTBRACKET: 79,# G5 (白, ']' 键)
}

print("正在预生成声音，这可能需要几秒钟...")
sounds = {}
for key, note in key_note_map.items():
    freq = midi_to_freq(note)
    sounds[key] = generate_piano_like_wave(freq)
print("就绪！")

active_channels = {}

# ---------- 界面绘制逻辑 ----------
MARGIN_TOP = 70       
MARGIN_BOTTOM = 40    
MARGIN_LEFT = 20
MARGIN_RIGHT = 20
KEYBOARD_HEIGHT = WINDOW_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

all_notes = set(key_note_map.values())
min_note, max_note = min(all_notes), max(all_notes)

def is_white(note):
    return (note % 12) in {0, 2, 4, 5, 7, 9, 11}

first_white = min_note
while not is_white(first_white): first_white -= 1
last_white = max_note
while not is_white(last_white): last_white += 1

white_notes = [n for n in range(first_white, last_white + 1) if is_white(n)]

total_white_keys = len(white_notes)
available_width = WINDOW_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
WHITE_KEY_WIDTH = available_width // total_white_keys
BLACK_KEY_WIDTH = int(WHITE_KEY_WIDTH * 0.6)
KEYBOARD_START_X = MARGIN_LEFT
KEYBOARD_START_Y = MARGIN_TOP

note_to_keys = {}
for key, note in key_note_map.items():
    note_to_keys.setdefault(note, []).append(key)

key_rects = {}

for i, note in enumerate(white_notes):
    x = KEYBOARD_START_X + i * WHITE_KEY_WIDTH
    rect = pygame.Rect(x, KEYBOARD_START_Y, WHITE_KEY_WIDTH, KEYBOARD_HEIGHT)
    if note in note_to_keys:
        for key in note_to_keys[note]:
            key_rects[key] = (rect, True)

black_note_mods = {1, 3, 6, 8, 10}
for i, note in enumerate(white_notes[:-1]):
    next_note = white_notes[i+1]
    diff = next_note - note
    black_note = None
    if diff == 2:
        black_note = note + 1
    elif diff == 3:
        for bn in (note+1, note+2):
            if bn % 12 in black_note_mods:
                black_note = bn
                break

    if black_note is not None and first_white <= black_note <= last_white:
        x = KEYBOARD_START_X + (i + 1) * WHITE_KEY_WIDTH - BLACK_KEY_WIDTH // 2
        y = KEYBOARD_START_Y + KEYBOARD_HEIGHT - int(KEYBOARD_HEIGHT * 0.6)
        rect = pygame.Rect(x, y, BLACK_KEY_WIDTH, int(KEYBOARD_HEIGHT * 0.6))
        if black_note in note_to_keys:
            for key in note_to_keys[black_note]:
                key_rects[key] = (rect, False)

font_key = pygame.font.Font(None, 22)      
font_jianpu = pygame.font.Font(None, 26)   
font_info = pygame.font.Font(None, 24)

def key_display_name(key):
    if key == pygame.K_LEFTBRACKET: return '['
    elif key == pygame.K_RIGHTBRACKET: return ']'
    elif key == pygame.K_EQUALS: return '='
    else:
        name = pygame.key.name(key)
        return name.upper() if len(name) == 1 else name

def midi_to_jianpu_display(note):
    mod = note % 12
    octave = (note // 12) - 1
    base = {0:'1', 2:'2', 4:'3', 5:'4', 7:'5', 9:'6', 11:'7'}.get(mod, '#')
    if base == '#': return '#'
    # 增加高低音区分
    if octave < 4: return f"-{base}"
    elif octave > 4: return f"+{base}"
    return base

# ---------- 主循环 ----------
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in sounds:
                if event.key in active_channels:
                    # 将旧通道淡出，防止咔哒声
                    active_channels[event.key].fadeout(100)
                # 【优化】：loops=0，让声音自然衰减结束，绝不循环
                ch = sounds[event.key].play(loops=0)
                if ch:
                    active_channels[event.key] = ch
        elif event.type == pygame.KEYUP:
            if event.key in active_channels:
                # 【优化】：模拟松开琴键后制音器压住琴弦的效果
                active_channels[event.key].fadeout(150)
                del active_channels[event.key]

    screen.fill((50, 50, 50))

    # 绘制背景与按键
    for key, (rect, is_white) in key_rects.items():
        if is_white:
            color = (220, 220, 220) if key not in active_channels else (255, 255, 0)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 2)

    for key, (rect, is_white) in key_rects.items():
        if not is_white:
            color = (80, 80, 80) if key not in active_channels else (255, 200, 0)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 2)

    # 标注字符
    for key, (rect, is_white) in key_rects.items():
        key_name = key_display_name(key)
        jianpu = midi_to_jianpu_display(key_note_map[key])
        
        key_surf = font_key.render(key_name, True, (0, 0, 0) if is_white else (255, 255, 255))
        key_rect = key_surf.get_rect(center=(rect.centerx, rect.centery - 15))
        screen.blit(key_surf, key_rect)
        
        jp_surf = font_jianpu.render(jianpu, True, (0, 0, 0) if is_white else (255, 255, 255))
        jp_rect = jp_surf.get_rect(center=(rect.centerx, rect.centery + 15))
        screen.blit(jp_surf, jp_rect)

    # 底部提示
    hint = font_info.render("底排(Z-M)低音区 | 顶排(Q-I)中音区 | 松开模拟制音器落下", True, (200, 200, 200))
    screen.blit(hint, (20, WINDOW_HEIGHT - 35))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()