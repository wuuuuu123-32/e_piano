import pygame
import sys
import os
import threading  # 用于延时停止

# ---------- 将当前目录添加到 PATH，使 fluidsynth 能找到 DLL ----------
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] = current_dir + os.pathsep + os.environ.get('PATH', '')

# ---------- 劫持 os.add_dll_directory 处理硬编码路径 ----------
original_add_dll_directory = os.add_dll_directory

def safe_add_dll_directory(path):
    if os.path.exists(path):
        return original_add_dll_directory(path)
    # 忽略不存在的路径

os.add_dll_directory = safe_add_dll_directory

# 现在导入 fluidsynth
import fluidsynth

# 恢复原函数
os.add_dll_directory = original_add_dll_directory

# 手动添加当前目录到 DLL 搜索路径
if hasattr(os, 'add_dll_directory'):
    try:
        os.add_dll_directory(current_dir)
    except FileNotFoundError:
        pass

# ---------- 初始化 Pygame ----------
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
pygame.init()

WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 500
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("e_piano - V3.0 sf2+自然余音版")

pygame.mixer.set_num_channels(128)

# ---------- 资源路径辅助函数 ----------
def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------- 初始化 FluidSynth ----------
fs = fluidsynth.Synth()
fs.start(driver="dsound")

sf2_path = resource_path("piano.sf2")
sfid = fs.sfload(sf2_path)
if sfid == -1:
    print("❌ 加载 SoundFont 失败，请检查 piano.sf2 文件")
    sys.exit(1)

fs.program_select(0, sfid, 0, 0)

# 设置增益（音量）
try:
    fs.setting("synth.gain", 0.8)
except AttributeError:
    try:
        fs.set_gain(0.8)
    except AttributeError:
        print("⚠️ 无法设置增益，使用默认音量")

# ---------- 键盘映射 ----------
key_note_map = {
    pygame.K_q: 48, pygame.K_w: 50, pygame.K_e: 52,
    pygame.K_a: 53, pygame.K_s: 55, pygame.K_d: 57,
    pygame.K_z: 59,
    pygame.K_r: 60, pygame.K_t: 62, pygame.K_y: 64,
    pygame.K_f: 65, pygame.K_g: 67, pygame.K_h: 69,
    pygame.K_v: 71,
    pygame.K_u: 72, pygame.K_i: 74, pygame.K_o: 76,
    pygame.K_j: 77, pygame.K_k: 79, pygame.K_l: 81,
    pygame.K_m: 83,
    pygame.K_COMMA: 84,
    pygame.K_1: 49, pygame.K_2: 51, pygame.K_3: 54, pygame.K_4: 56, pygame.K_5: 58,
    pygame.K_6: 61, pygame.K_7: 63, pygame.K_8: 66, pygame.K_9: 68, pygame.K_0: 70,
}

# ---------- 状态追踪 ----------
active_notes = {}      # 当前正在发声的音符（包括延迟停止的？不，延迟停止后会从 active_notes 移除）
pedal_active = False
stop_timers = {}       # 用于延迟停止的定时器

def cancel_stop_timer(key):
    if key in stop_timers:
        stop_timers[key].cancel()
        del stop_timers[key]

def delayed_noteoff(key, note, delay_ms=400):
    """延迟发送 noteoff，模拟自然衰减"""
    def stop():
        # 确保该键仍在 active_notes 中（可能已被其他操作移除）
        if key in active_notes and active_notes[key] == note:
            fs.noteoff(0, note)
            del active_notes[key]
        if key in stop_timers:
            del stop_timers[key]

    timer = threading.Timer(delay_ms / 1000.0, stop)
    timer.daemon = True
    stop_timers[key] = timer
    timer.start()

# ---------- 绘图辅助 ----------
all_notes = sorted(list(set(key_note_map.values())))
white_notes = [n for n in range(min(all_notes), max(all_notes)+1) if (n%12) in {0,2,4,5,7,9,11}]
note_to_keys = {v: [k for k, val in key_note_map.items() if val == v] for v in all_notes}
font_key = pygame.font.Font(None, 20); font_jp = pygame.font.Font(None, 24)

def get_jp_name(n):
    """简谱数字显示，+ 表示高八度，- 表示低八度，个数表示偏移量"""
    mod, octv = n % 12, (n // 12) - 1
    name = {0:'1', 2:'2', 4:'3', 5:'4', 7:'5', 9:'6', 11:'7'}.get(mod, '#')
    if name == '#':
        return '#'
    diff = octv - 4   # 以 C4 为基准
    if diff < 0:
        return '-' * (-diff) + name
    elif diff > 0:
        return '+' * diff + name
    else:
        return name

# ---------- 主循环 ----------
clock = pygame.time.Clock()
print("SoundFont 版已启动（自然余音版），空格键控制延音踏板")

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            # 退出前取消所有定时器
            for timer in stop_timers.values():
                timer.cancel()
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                pedal_active = True
                fs.cc(0, 64, 127)
            elif event.key in key_note_map:
                note = key_note_map[event.key]
                # 如果该键已经在响（包括延迟停止中），取消旧定时器并立即停止旧音
                if event.key in active_notes:
                    cancel_stop_timer(event.key)
                    fs.noteoff(0, active_notes[event.key])
                # 播放新音
                fs.noteon(0, note, 100)
                active_notes[event.key] = note

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE:
                pedal_active = False
                fs.cc(0, 64, 0)
                # 松开踏板时，所有没有被物理按下的键应该停止（取消定时器并立即 noteoff）
                for k in list(active_notes.keys()):
                    if not pygame.key.get_pressed()[k]:
                        cancel_stop_timer(k)
                        fs.noteoff(0, active_notes[k])
                        del active_notes[k]
            elif event.key in active_notes:
                if pedal_active:
                    # 踏板踩下：不停止，也不设定时器，让声音持续
                    pass
                else:
                    # 不踩踏板：取消可能存在的旧定时器，然后启动新定时器
                    cancel_stop_timer(event.key)
                    delayed_noteoff(event.key, active_notes[event.key], delay_ms=400)

    # --- 绘制界面（与原代码相同，仅判断来源改为 active_notes）---
    screen.fill((30, 33, 40))
    w_width = WINDOW_WIDTH // len(white_notes)

    for i, n in enumerate(white_notes):
        rect = pygame.Rect(i * w_width, 100, w_width, 300)
        is_playing = n in [key_note_map[k] for k in active_notes]
        pygame.draw.rect(screen, (255, 230, 150) if is_playing else (230, 230, 230), rect)
        pygame.draw.rect(screen, (0, 0, 0), rect, 1)

        if n in note_to_keys:
            k_txt = "/".join([pygame.key.name(k).upper() for k in note_to_keys[n]])
            txt = font_key.render(k_txt, True, (80, 80, 80))
            screen.blit(txt, txt.get_rect(center=(rect.centerx, 350)))
            jp = font_jp.render(get_jp_name(n), True, (0, 0, 0))
            screen.blit(jp, jp.get_rect(center=(rect.centerx, 375)))

    for i, n in enumerate(white_notes[:-1]):
        if (n % 12) in {0, 2, 5, 7, 9}:
            bn = n + 1
            rect = pygame.Rect(i * w_width + w_width*0.7, 100, w_width*0.6, 180)
            is_playing = bn in [key_note_map[k] for k in active_notes]
            pygame.draw.rect(screen, (255, 120, 0) if is_playing else (20, 20, 20), rect)

    pedal_color = (0, 255, 0) if pedal_active else (100, 100, 100)
    status_txt = "SUSTAIN PEDAL (SPACE)"
    txt = font_jp.render(status_txt, True, pedal_color)
    screen.blit(txt, (WINDOW_WIDTH - 250, 30))

    info = font_jp.render("sf2自然余音版 | 松开键后有尾音 | 踏板正常", True, (200, 200, 200))
    screen.blit(info, (20, 20))

    pygame.display.flip()
    clock.tick(60)