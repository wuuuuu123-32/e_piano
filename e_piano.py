import pygame
import sys
import os
import threading

# ---------- 路径与 DLL 处理 ----------
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] = current_dir + os.pathsep + os.environ.get('PATH', '')

original_add_dll_directory = os.add_dll_directory
def safe_add_dll_directory(path):
    if os.path.exists(path): return original_add_dll_directory(path)
os.add_dll_directory = safe_add_dll_directory

import fluidsynth
os.add_dll_directory = original_add_dll_directory

if hasattr(os, 'add_dll_directory'):
    try: os.add_dll_directory(current_dir)
    except FileNotFoundError: pass

# ---------- 初始化 ----------
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
pygame.init()

WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 500
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("e_piano - V3.5 矩阵黑键补齐版")

def resource_path(relative_path):
    if getattr(sys, 'frozen', False): base_path = sys._MEIPASS
    else: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

fs = fluidsynth.Synth()
fs.start(driver="dsound")
sf2_path = resource_path("piano.sf2")
sfid = fs.sfload(sf2_path)
if sfid == -1:
    print("❌ 找不到 piano.sf2"); sys.exit(1)
fs.program_select(0, sfid, 0, 0)
fs.setting("synth.gain", 0.8)

# ================= 核心更新：补齐矩阵黑键 =================

# 1. 矩阵模式 (现在最右侧的符号键也被映射为高音黑键)
layout_matrix = {
    # 白键部分
    pygame.K_q: 48, pygame.K_w: 50, pygame.K_e: 52, pygame.K_a: 53, pygame.K_s: 55, pygame.K_d: 57, pygame.K_z: 59,
    pygame.K_r: 60, pygame.K_t: 62, pygame.K_y: 64, pygame.K_f: 65, pygame.K_g: 67, pygame.K_h: 69, pygame.K_v: 71,
    pygame.K_u: 72, pygame.K_i: 74, pygame.K_o: 76, pygame.K_j: 77, pygame.K_k: 79, pygame.K_l: 81, pygame.K_m: 83,
    pygame.K_COMMA: 84,
    
    # 黑键部分 (补齐了最后五个符号键)
    pygame.K_1: 49, pygame.K_2: 51, pygame.K_3: 54, pygame.K_4: 56, pygame.K_5: 58,
    pygame.K_6: 61, pygame.K_7: 63, pygame.K_8: 66, pygame.K_9: 68, pygame.K_0: 70,
    pygame.K_MINUS: 73, pygame.K_EQUALS: 75, pygame.K_LEFTBRACKET: 78, pygame.K_RIGHTBRACKET: 80, pygame.K_BACKSLASH: 82
}

# 2. 线性模式 (三层音区，保持 V3.4 逻辑)
layout_linear = {
    pygame.K_z: 48, pygame.K_x: 50, pygame.K_c: 52, pygame.K_v: 53, pygame.K_b: 55, pygame.K_n: 57, pygame.K_m: 59,
    pygame.K_a: 60, pygame.K_s: 62, pygame.K_d: 64, pygame.K_f: 65, pygame.K_g: 67, pygame.K_h: 69, pygame.K_j: 71,
    pygame.K_q: 72, pygame.K_w: 74, pygame.K_e: 76, pygame.K_r: 77, pygame.K_t: 79, pygame.K_y: 81, pygame.K_u: 83,
    pygame.K_i: 84, 
    
    pygame.K_1: 49, pygame.K_2: 51, pygame.K_3: 54, pygame.K_4: 56, pygame.K_5: 58,
    pygame.K_6: 61, pygame.K_7: 63, pygame.K_8: 66, pygame.K_9: 68, pygame.K_0: 70,
    pygame.K_MINUS: 73, pygame.K_EQUALS: 75, pygame.K_LEFTBRACKET: 78, pygame.K_RIGHTBRACKET: 80, pygame.K_BACKSLASH: 82
}

# =========================================================

current_mode = "MATRIX"
key_note_map = {}
all_notes = []
white_notes = []
note_to_keys = {}

def apply_layout(layout_dict):
    global key_note_map, all_notes, white_notes, note_to_keys
    key_note_map = layout_dict
    all_notes = sorted(list(set(key_note_map.values())))
    white_notes = [n for n in range(min(all_notes), max(all_notes)+1) if (n%12) in {0,2,4,5,7,9,11}]
    note_to_keys = {v: [k for k, val in key_note_map.items() if val == v] for v in all_notes}

apply_layout(layout_matrix)

active_notes = {}      
pedal_active = False
stop_timers = {}       

def cancel_stop_timer(key):
    if key in stop_timers:
        stop_timers[key].cancel()
        del stop_timers[key]

def delayed_noteoff(key, note, delay_ms=400):
    def stop():
        if key in active_notes and active_notes[key] == note:
            fs.noteoff(0, note)
            del active_notes[key]
        if key in stop_timers: del stop_timers[key]
    timer = threading.Timer(delay_ms / 1000.0, stop)
    timer.daemon = True
    stop_timers[key] = timer
    timer.start()

font_key = pygame.font.Font(None, 20); font_jp = pygame.font.Font(None, 24); font_title = pygame.font.Font(None, 30)

def get_jp_name(n):
    mod, octv = n % 12, (n // 12) - 1
    name = {0:'1', 2:'2', 4:'3', 5:'4', 7:'5', 9:'6', 11:'7'}.get(mod, '#')
    if name == '#': return '#'
    diff = octv - 4  
    if diff < 0: return '-' * (-diff) + name
    elif diff > 0: return '+' * diff + name
    else: return name

clock = pygame.time.Clock()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            for timer in stop_timers.values(): timer.cancel()
            pygame.quit(); sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                for k, note in list(active_notes.items()):
                    cancel_stop_timer(k)
                    fs.noteoff(0, note)
                active_notes.clear()
                current_mode = "LINEAR" if current_mode == "MATRIX" else "MATRIX"
                apply_layout(layout_linear if current_mode == "LINEAR" else layout_matrix)
            elif event.key == pygame.K_SPACE:
                pedal_active = True
                fs.cc(0, 64, 127)
            elif event.key in key_note_map:
                note = key_note_map[event.key]
                if event.key in active_notes:
                    cancel_stop_timer(event.key)
                    fs.noteoff(0, active_notes[event.key])
                fs.noteon(0, note, 100)
                active_notes[event.key] = note

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE:
                pedal_active = False
                fs.cc(0, 64, 0)
                for k in list(active_notes.keys()):
                    if not pygame.key.get_pressed()[k]:
                        cancel_stop_timer(k)
                        fs.noteoff(0, active_notes[k])
                        del active_notes[k]
            elif event.key in active_notes:
                if not pedal_active:
                    cancel_stop_timer(event.key)
                    delayed_noteoff(event.key, active_notes[event.key], delay_ms=400)

    # --- 绘图逻辑 (支持黑键按键提示) ---
    screen.fill((30, 33, 40))
    w_width = WINDOW_WIDTH // len(white_notes)

    for i, n in enumerate(white_notes):
        rect = pygame.Rect(i * w_width, 100, w_width, 300)
        is_playing = n in [key_note_map[k] for k in active_notes]
        pygame.draw.rect(screen, (255, 230, 150) if is_playing else (230, 230, 230), rect)
        pygame.draw.rect(screen, (0, 0, 0), rect, 1)

        if n in note_to_keys:
            keys_str = ",".join([pygame.key.name(k).upper() for k in note_to_keys[n]])
            txt = font_key.render(keys_str[:9], True, (80, 80, 80))
            screen.blit(txt, txt.get_rect(center=(rect.centerx, 350)))
            jp = font_jp.render(get_jp_name(n), True, (0, 0, 0))
            screen.blit(jp, jp.get_rect(center=(rect.centerx, 375)))

    for i, n in enumerate(white_notes[:-1]):
        if (n % 12) in {0, 2, 5, 7, 9}:
            bn = n + 1
            rect = pygame.Rect(i * w_width + w_width*0.7, 100, w_width*0.6, 180)
            is_playing = bn in [key_note_map[k] for k in active_notes]
            pygame.draw.rect(screen, (255, 120, 0) if is_playing else (20, 20, 20), rect)
            if bn in note_to_keys:
                b_keys = ",".join([pygame.key.name(k).upper() for k in note_to_keys[bn]])
                b_txt = font_key.render(b_keys[:8], True, (220, 220, 220))
                screen.blit(b_txt, b_txt.get_rect(center=(rect.centerx, 260)))

    # --- 状态栏 ---
    pedal_color = (0, 255, 0) if pedal_active else (100, 100, 100)
    screen.blit(font_jp.render("SUSTAIN (SPACE)", True, pedal_color), (WINDOW_WIDTH - 200, 30))
    mode_text = "矩阵布局 (黑键补齐)" if current_mode == "MATRIX" else "线性布局 (三层音区)"
    screen.blit(font_title.render(f"当前模式: {mode_text}", True, (255, 255, 255)), (20, 20))
    screen.blit(font_jp.render("[TAB] 切换模式 | [SPACE] 延音踏板", True, (170, 170, 170)), (20, 55))

    pygame.display.flip()
    clock.tick(60)