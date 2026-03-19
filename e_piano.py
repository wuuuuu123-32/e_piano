import pygame
import numpy as np
import sys

# ---------- 初始化 Pygame ----------
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
pygame.init()

# 窗口大小（可根据需要调整）
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 500
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("e_piano - 钢琴音色 + 简谱引导")

pygame.mixer.set_num_channels(32)

# ---------- 声音合成参数 ----------
SAMPLE_RATE = 44100
DURATION = 5.0  # 每个音符的采样长度（用于循环播放）

def midi_to_freq(note):
    """MIDI音符编号 -> 频率(Hz)"""
    return 440 * (2 ** ((note - 69) / 12))

def generate_piano_like_wave(freq, duration=DURATION):
    """
    生成具有 Attack-Decay-Sustain 包络的波形，适合循环播放。
    - Attack: 0 -> 1, 5ms
    - Decay: 1 -> sustain_level, 200ms
    - Sustain: 保持 sustain_level
    - Release 由 KEYUP 的 fadeout 处理
    """
    frames = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, frames, endpoint=False)
    wave = np.zeros(frames)

    # 动态参数（与之前类似）
    pitch_ratio = np.clip(freq / 261.63, 0.5, 4.0)
    base_decay = 2.5 * pitch_ratio  # 用于泛音衰减（非包络）

    # 三弦 detuning
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
            # 泛音自身的指数衰减（模拟琴弦能量损失）
            decay_rate = 1.0 + (n * 0.5)
            harmonic_env = np.exp(-decay_rate * t * base_decay)
            wave += amplitude * harmonic_env * np.sin(2 * np.pi * f_n * t)

    # 琴槌敲击噪声
    attack_noise_len = int(max(0.005, 0.03 / pitch_ratio) * SAMPLE_RATE)
    if attack_noise_len > 0:
        noise_amp = 0.2 / pitch_ratio
        noise = np.random.normal(0, noise_amp, attack_noise_len)
        noise_envelope = np.exp(-np.linspace(0, 8, attack_noise_len))
        wave[:attack_noise_len] += noise * noise_envelope

    # 归一化
    wave = wave / np.max(np.abs(wave))

    # ========== 新增：Attack-Decay-Sustain 包络 ==========
    attack_len = int(0.005 * SAMPLE_RATE)      # 5ms attack
    decay_len = int(0.2 * SAMPLE_RATE)         # 200ms decay
    sustain_level = 0.5                         # 持续电平

    envelope = np.ones(frames)
    # Attack: 线性上升
    envelope[:attack_len] = np.linspace(0, 1, attack_len)
    # Decay: 指数下降
    if decay_len > 0:
        decay_curve = np.exp(-np.linspace(0, 3, decay_len))  # 指数形状，范围 1 -> ~0.05
        # 缩放 decay_curve 从 [1, ~0.05] 到 [1, sustain_level]
        decay_curve = 1 - (1 - sustain_level) * (1 - decay_curve)
        envelope[attack_len:attack_len+decay_len] = decay_curve
    # Sustain: 保持恒定
    envelope[attack_len+decay_len:] = sustain_level

    wave *= envelope
    # ==================================================

    # 转换为 16-bit PCM
    wave = (wave * 32767).astype(np.int16)
    stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
    return pygame.sndarray.make_sound(stereo)




# ---------- 键盘映射 ----------
key_note_map = {
    # 白键（第二排字母）
    pygame.K_a: 60,   # C4
    pygame.K_s: 62,   # D4
    pygame.K_d: 64,   # E4
    pygame.K_f: 65,   # F4
    pygame.K_g: 67,   # G4
    pygame.K_h: 69,   # A4
    pygame.K_j: 71,   # B4
    pygame.K_k: 72,   # C5
    pygame.K_l: 74,   # D5
    pygame.K_SEMICOLON: 76,  # E5 (; 键)
    pygame.K_QUOTE: 77,      # F5 (' 键)
    pygame.K_RETURN: 79,     # G5 (回车键，可选)

    # 黑键（第一排字母）
    pygame.K_w: 61,   # C#4
    pygame.K_e: 63,   # D#4
    pygame.K_t: 66,   # F#4
    pygame.K_y: 68,   # G#4
    pygame.K_u: 70,   # A#4
    pygame.K_o: 73,   # C#5
    pygame.K_p: 75,   # D#5
}

# 预生成所有音符的声音
sounds = {}
for key, note in key_note_map.items():
    freq = midi_to_freq(note)
    sounds[key] = generate_piano_like_wave(freq)

# 当前正在播放的通道
active_channels = {}

# ---------- 键盘绘制参数（自适应宽度）----------
MARGIN_TOP = 70       # 顶部留白（给简谱条）
MARGIN_BOTTOM = 40    # 底部留白
MARGIN_LEFT = 20
MARGIN_RIGHT = 20
KEYBOARD_HEIGHT = WINDOW_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# 获取所有映射的音符
all_notes = set(key_note_map.values())
min_note = min(all_notes)
max_note = max(all_notes)

def is_white(note):
    return (note % 12) in {0, 2, 4, 5, 7, 9, 11}

# 找到最左和最右的白键（用于绘制完整键盘）
first_white = min_note
while not is_white(first_white):
    first_white -= 1
last_white = max_note
while not is_white(last_white):
    last_white += 1

# 生成白键列表
white_notes = []
note = first_white
while note <= last_white:
    if is_white(note):
        white_notes.append(note)
    note += 1

# 根据窗口宽度自动计算白键宽度
total_white_keys = len(white_notes)
available_width = WINDOW_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
WHITE_KEY_WIDTH = available_width // total_white_keys
BLACK_KEY_WIDTH = int(WHITE_KEY_WIDTH * 0.6)
KEYBOARD_START_X = MARGIN_LEFT
KEYBOARD_START_Y = MARGIN_TOP

# 反向映射：音符 -> 按键列表（用于绘制）
note_to_keys = {}
for key, note in key_note_map.items():
    note_to_keys.setdefault(note, []).append(key)

key_rects = {}  # key -> (rect, is_white)

# 绘制白键并记录矩形
for i, note in enumerate(white_notes):
    x = KEYBOARD_START_X + i * WHITE_KEY_WIDTH
    rect = pygame.Rect(x, KEYBOARD_START_Y, WHITE_KEY_WIDTH, KEYBOARD_HEIGHT)
    if note in note_to_keys:
        for key in note_to_keys[note]:
            key_rects[key] = (rect, True)  # True 表示白键

# 绘制黑键
black_note_mods = {1, 3, 6, 8, 10}
for i, note in enumerate(white_notes[:-1]):  # 最后一个白键后面无黑键
    next_note = white_notes[i+1]
    diff = next_note - note
    if diff == 2:
        black_note = note + 1
    elif diff == 3:
        # 可能有两个黑键？标准钢琴布局中，只有 C-D, D-E, F-G, G-A, A-B 之间有黑键
        # 这里简单检查模数
        black_note = None
        for bn in (note+1, note+2):
            if bn % 12 in black_note_mods:
                black_note = bn
                break
    else:
        black_note = None

    if black_note is not None and first_white <= black_note <= last_white:
        x = KEYBOARD_START_X + (i + 1) * WHITE_KEY_WIDTH - BLACK_KEY_WIDTH // 2
        y = KEYBOARD_START_Y + KEYBOARD_HEIGHT - int(KEYBOARD_HEIGHT * 0.6)  # 黑键底部对齐
        rect = pygame.Rect(x, y, BLACK_KEY_WIDTH, int(KEYBOARD_HEIGHT * 0.6))
        if black_note in note_to_keys:
            for key in note_to_keys[black_note]:
                key_rects[key] = (rect, False)

# ---------- 字体 ----------
font_key = pygame.font.Font(None, 20)      # 用于按键名
font_jianpu = pygame.font.Font(None, 28)   # 用于简谱数字
font_info = pygame.font.Font(None, 24)

def key_display_name(key):
    """将 pygame 按键常量转换为可读字符"""
    if key == pygame.K_SEMICOLON:
        return ';'
    elif key == pygame.K_QUOTE:
        return "'"
    elif key == pygame.K_RETURN:
        return '↵'
    else:
        name = pygame.key.name(key)
        return name.upper() if len(name) == 1 else name

def midi_to_jianpu_display(note):
    """
    返回简谱显示字符：
    - 白键：数字 1-7
    - 黑键：'#' (表示升号)
    """
    mod = note % 12
    if mod == 0: return '1'
    elif mod == 2: return '2'
    elif mod == 4: return '3'
    elif mod == 5: return '4'
    elif mod == 7: return '5'
    elif mod == 9: return '6'
    elif mod == 11: return '7'
    else: return '#'  # 黑键

def draw_jianpu_bar(screen):
    """在顶部绘制简谱提示条"""
    bar_y = 5
    bar_height = 35
    pygame.draw.rect(screen, (60, 60, 60), (0, bar_y, WINDOW_WIDTH, bar_height))
    
    # 显示简谱数字 1-7 及其对应的音名
    jianpu_chars = ['1', '2', '3', '4', '5', '6', '7']
    note_names = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
    step = WINDOW_WIDTH // 8
    
    for i, (num, name) in enumerate(zip(jianpu_chars, note_names)):
        x = (i + 1) * step
        # 大数字
        num_surf = font_jianpu.render(num, True, (255, 255, 100))
        num_rect = num_surf.get_rect(center=(x, bar_y + bar_height//2 - 5))
        screen.blit(num_surf, num_rect)
        # 小音名
        name_surf = font_key.render(name, True, (200, 200, 200))
        name_rect = name_surf.get_rect(center=(x, bar_y + bar_height//2 + 12))
        screen.blit(name_surf, name_rect)
    
    # 说明文字
    hint = font_info.render("简谱数字对照 (C大调)  黑键显示 #", True, (200, 200, 200))
    screen.blit(hint, (10, bar_y + bar_height + 2))

# ---------- 主循环 ----------
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in sounds:
                # 如果该键已经在播放，先淡出停止
                if event.key in active_channels:
                    active_channels[event.key].fadeout(50)
                # 播放新声音（无限循环）
                ch = sounds[event.key].play(loops=-1)
                if ch:
                    active_channels[event.key] = ch
               # print(f"按下: {key_note_map[event.key]}")
        elif event.type == pygame.KEYUP:
            if event.key in active_channels:
                active_channels[event.key].fadeout(50)   # 50ms淡出
                del active_channels[event.key]
               # print(f"松开: {key_note_map.get(event.key, 'unknown')}")

    # 绘制背景
    screen.fill((50, 50, 50))

    # 绘制白键（先画，让黑键覆盖）
    for key, (rect, is_white) in key_rects.items():
        if is_white:
            color = (220, 220, 220) if key not in active_channels else (255, 255, 0)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 2)  # 黑色边框

    # 绘制黑键
    for key, (rect, is_white) in key_rects.items():
        if not is_white:
            color = (80, 80, 80) if key not in active_channels else (255, 200, 0)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 2)

    # 在琴键上标注按键名和简谱数字
    for key, (rect, is_white) in key_rects.items():
        note = key_note_map[key]
        key_name = key_display_name(key)
        jianpu = midi_to_jianpu_display(note)
        
        # 按键名（小字，放在上半部分）
        key_surf = font_key.render(key_name, True, (0, 0, 0) if is_white else (255, 255, 255))
        key_rect = key_surf.get_rect(center=(rect.centerx, rect.centery - 15))
        screen.blit(key_surf, key_rect)
        
        # 简谱数字（大字，放在下半部分）
        jp_surf = font_jianpu.render(jianpu, True, (0, 0, 0) if is_white else (255, 255, 255))
        jp_rect = jp_surf.get_rect(center=(rect.centerx, rect.centery + 15))
        screen.blit(jp_surf, jp_rect)

    # 绘制顶部简谱提示条
    draw_jianpu_bar(screen)

    # 底部提示
    hint = font_info.render("按字母键演奏，松开停止", True, (200, 200, 200))
    screen.blit(hint, (20, WINDOW_HEIGHT - 25))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()