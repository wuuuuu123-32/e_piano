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
                print(f"按下: {key_note_map[event.key]}")
        elif event.type == pygame.KEYUP:
            if event.key in active_channels:
                active_channels[event.key].fadeout(50)   # 50ms淡出
                del active_channels[event.key]
                print(f"松开: {key_note_map.get(event.key, 'unknown')}")

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