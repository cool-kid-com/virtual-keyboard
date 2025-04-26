import pygame
import asyncio
import platform
import math
import uuid
import copy
import time
import traceback
import json


js = None


def setup(width=1200, height=400, fullscreen=False):
    global screen, font, small_font, tiny_font, state, keyboards, selected_key, swipe_start, swipe_direction, selected_keyboard, current_keys, dragged_key, configuring_key, label_text, text_active, active_input, action_texts, scroll_offset, max_scroll, dragged_scroll, keyboard_name_text, last_typed_text, SPECIAL_KEYS, last_arrow_click, input_buffer, show_keyboard, scroll_start_y, load_code_text, active_modifiers, caps_lock_active
    pygame.init()
    flags = pygame.RESIZABLE
    if fullscreen:
        flags |= pygame.FULLSCREEN
        screen = pygame.display.set_mode((0, 0), flags)
    else:
        screen = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("Virtual Touchscreen Keyboard")
    font = pygame.font.SysFont("arial", 14)
    small_font = pygame.font.SysFont("arial", 10)
    tiny_font = pygame.font.SysFont("arial", 8)
   
    state = "start"
    keyboards = []
    selected_key = None
    swipe_start = None
    swipe_direction = None
    selected_keyboard = None
    current_keys = []
    dragged_key = None
    configuring_key = None
    label_text = ""
    text_active = False
    active_input = None
    action_texts = {}
    scroll_offset = 0
    max_scroll = 0
    dragged_scroll = False
    keyboard_name_text = ""
    last_typed_text = ""
    input_buffer = ""
    show_keyboard = False
    scroll_start_y = 0
    load_code_text = ""
    active_modifiers = {"Shift": False, "Ctrl": False, "Alt": False}
    caps_lock_active = False
    SPECIAL_KEYS = [
        "", "Shift", "Ctrl", "Alt", "Tab", "Enter", "Backspace", "Space",
        "Esc", "Delete", "CapsLock", "Fn", "Windows", "Up", "Down", "Left", "Right"
    ]
    last_arrow_click = 0


DIRECTIONS = ["Tap", "Up", "Down", "Left", "Right", "Up-Left", "Up-Right", "Down-Left", "Down-Right"]


def copy_to_clipboard(text):
    if platform.system() == "Emscripten":
        try:
            escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
            js.eval(f'navigator.clipboard.writeText("{escaped_text}")')
            js.eval(f'console.log("Clipboard success: {escaped_text[:50]}...")')
        except Exception as e:
            js.eval(f'console.error("Clipboard error: {str(e)}")')
    else:
        try:
            import pyperclip # type: ignore
            pyperclip.copy(text)
        except ImportError:
            try:
                # Fallback to pygame clipboard if pyperclip is not available
                pygame.scrap.init()
                pygame.scrap.put(pygame.SCRAP_TEXT, text.encode('utf-8'))
            except Exception as e:
                print(f"Clipboard error: {e}")


def get_clipboard_text():
    if platform.system() == "Emscripten":
        try:
            return js.eval('navigator.clipboard.readText()')
        except Exception as e:
            js.eval(f'console.error("Clipboard read error: {str(e)}")')
            return ""
    else:
        try:
            import pyperclip # type: ignore
            return pyperclip.paste()
        except ImportError:
            try:
                # Fallback to pygame clipboard if pyperclip is not available
                pygame.scrap.init()
                text = pygame.scrap.get(pygame.SCRAP_TEXT)
                return text.decode('utf-8') if text else ""
            except Exception as e:
                print(f"Clipboard read error: {e}")
                return ""


def send_key(text):
    global input_buffer, active_modifiers, caps_lock_active
   
    # Handle CapsLock
    if text == "CapsLock":
        caps_lock_active = not caps_lock_active
        return
   
    # Handle modifier keys
    if text in ["Shift", "Ctrl", "Alt"]:
        active_modifiers[text] = True
        return
   
    if platform.system() != "Emscripten":
        # Handle special keys and shortcuts in native mode
        if text == "Backspace":
            input_buffer = input_buffer[:-1]
            return
        elif text == "Space":
            text = " "
        elif text == "Enter":
            text = "\n"
        elif text == "Tab":
            text = "\t"
        elif text == "Delete":
            input_buffer = ""
            return
        elif text == "Esc":
            # Clear current input
            input_buffer = ""
            return
       
        # Apply modifiers
        if active_modifiers["Shift"] or caps_lock_active:
            text = text.upper()
       
        # Handle Ctrl shortcuts
        if active_modifiers["Ctrl"] and len(text) == 1:
            text_lower = text.lower()
            if text_lower == "c":  # Copy
                copy_to_clipboard(input_buffer)
                text = ""
            elif text_lower == "v":  # Paste
                try:
                    pasted_text = get_clipboard_text()
                    input_buffer += pasted_text
                    text = ""
                except:
                    text = ""
            elif text_lower == "x":  # Cut
                copy_to_clipboard(input_buffer)
                input_buffer = ""
                text = ""
            elif text_lower == "a":  # Select all (simulated by copying all)
                copy_to_clipboard(input_buffer)
                text = ""
            elif text_lower == "z":  # Clear (instead of undo)
                input_buffer = ""
                text = ""
            else:
                text = f"^{text}"
       
        input_buffer += text
        # Reset modifiers after key press (except CapsLock)
        active_modifiers = {"Shift": False, "Ctrl": False, "Alt": False}
        return
   
    try:
        key_map = {
            "Enter": {"key": "Enter", "code": "Enter", "keyCode": 13},
            "Backspace": {"key": "Backspace", "code": "Backspace", "keyCode": 8},
            "Space": {"key": " ", "code": "Space", "keyCode": 32},
            "Tab": {"key": "Tab", "code": "Tab", "keyCode": 9},
            "Shift": {"key": "Shift", "code": "ShiftLeft", "keyCode": 16, "shiftKey": True},
            "Ctrl": {"key": "Control", "code": "ControlLeft", "keyCode": 17, "ctrlKey": True},
            "Alt": {"key": "Alt", "code": "AltLeft", "keyCode": 18, "altKey": True},
            "Esc": {"key": "Escape", "code": "Escape", "keyCode": 27},
            "Delete": {"key": "Delete", "code": "Delete", "keyCode": 46},
            "CapsLock": {"key": "CapsLock", "code": "CapsLock", "keyCode": 20},
            "Fn": {"key": "Fn", "code": "Fn"},
            "Windows": {"key": "Meta", "code": "MetaLeft", "keyCode": 91, "metaKey": True},
            "Up": {"key": "ArrowUp", "code": "ArrowUp", "keyCode": 38},
            "Down": {"key": "ArrowDown", "code": "ArrowDown", "keyCode": 40},
            "Left": {"key": "ArrowLeft", "code": "ArrowLeft", "keyCode": 37},
            "Right": {"key": "ArrowRight", "code": "ArrowRight", "keyCode": 39}
        }
       
        # Apply modifiers to the key event
        if text in key_map:
            props = key_map[text]
        else:
            if active_modifiers["Shift"] or caps_lock_active:
                text = text.upper()
            props = {"key": text, "code": f"Key{text.upper()}", "keyCode": ord(text.upper())}
       
        # Add active modifiers to the key event
        props["shiftKey"] = active_modifiers["Shift"]
        props["ctrlKey"] = active_modifiers["Ctrl"]
        props["altKey"] = active_modifiers["Alt"]
       
        js_code = f'''
        let el = document.activeElement;
        if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {{
            ["keydown", "keypress", "keyup"].forEach(eventType =>
                el.dispatchEvent(new KeyboardEvent(eventType, {{
                    key: "{props['key']}",
                    code: "{props.get('code', '')}",
                    keyCode: {props.get('keyCode', 0)},
                    shiftKey: {str(props.get('shiftKey', False)).lower()},
                    ctrlKey: {str(props.get('ctrlKey', False)).lower()},
                    altKey: {str(props.get('altKey', False)).lower()},
                    metaKey: {str(props.get('metaKey', False)).lower()}
                }}))
            );
           
            // Handle special key combinations
            if ("{text}".match(/^[a-zA-Z]$/) && {str(props.get('ctrlKey', False)).lower()}) {{
                let key = "{text}".toLowerCase();
                if (key === "c") {{
                    // Copy
                    let text = el.value.substring(el.selectionStart, el.selectionEnd);
                    navigator.clipboard.writeText(text);
                }} else if (key === "v") {{
                    // Paste
                    navigator.clipboard.readText().then(text => {{
                        let start = el.selectionStart;
                        el.value = el.value.substring(0, start) + text + el.value.substring(el.selectionEnd);
                        el.selectionStart = el.selectionEnd = start + text.length;
                    }});
                }} else if (key === "x") {{
                    // Cut
                    let text = el.value.substring(el.selectionStart, el.selectionEnd);
                    navigator.clipboard.writeText(text);
                    let start = el.selectionStart;
                    el.value = el.value.substring(0, start) + el.value.substring(el.selectionEnd);
                    el.selectionStart = el.selectionEnd = start;
                }} else if (key === "a") {{
                    // Select all
                    el.select();
                }} else if (key === "z") {{
                    // Clear instead of undo
                    el.value = "";
                }}
            }} else if (!"{text}".match(/^(Shift|Ctrl|Alt)$/)) {{
                if ("{text}" === "Enter") {{
                    el.value += "\\n";
                }} else if ("{text}" === "Tab") {{
                    el.value += "\\t";
                }} else if ("{text}" === "Space") {{
                    el.value += " ";
                }} else if ("{text}" === "Backspace") {{
                    let start = el.selectionStart;
                    if (start > 0) {{
                        el.value = el.value.substring(0, start - 1) + el.value.substring(start);
                        el.selectionStart = el.selectionEnd = start - 1;
                    }}
                }} else if ("{text}" === "Delete") {{
                    el.value = "";
                }} else if ("{text}" === "Esc") {{
                    el.value = "";
                }} else {{
                    el.value += "{text}";
                }}
            }}
        }}
        '''
        js.eval(js_code)
       
        # Reset modifiers after key press unless it's a modifier key
        if text not in ["Shift", "Ctrl", "Alt"]:
            active_modifiers = {"Shift": False, "Ctrl": False, "Alt": False}
           
    except Exception as e:
        print(f"Key send error: {e}")
        input_buffer += text


def create_default_keyboard():
    keyboard = create_new_keyboard()
    keyboard["name"] = "QWERTY Keyboard"
    keyboard["keys"] = []  # Start with no keys
    return keyboard


def create_new_keyboard():
    keyboard_id = str(uuid.uuid4())
    return {"id": keyboard_id, "name": "New Keyboard", "keys": []}


def create_new_key(last_key=None):
    if last_key:
        new_key = copy.deepcopy(last_key)
        new_key["x"] = min(new_key["x"] + 10, 800 - new_key["width"])
        new_key["y"] = min(new_key["y"] + 10, 360 - new_key["height"])
        return new_key
    actions = {direction: "" for direction in DIRECTIONS}
    return {"char": "Key", "x": 40, "y": 40, "width": 40, "height": 40, "actions": actions}


def draw_start_screen():
    screen.fill((255, 255, 255))
    button_rect = pygame.Rect(300, 150, 150, 40)
    pygame.draw.rect(screen, (100, 100, 255), button_rect)
    pygame.draw.rect(screen, (0, 0, 0), button_rect, 1)
    text = font.render("Add Keyboard", True, (0, 0, 0))
    text_rect = text.get_rect(center=button_rect.center)
    screen.blit(text, text_rect)
   
    if platform.system() == "Emscripten":
        js.eval(f'console.log("Start screen: Add rect={button_rect}")')
   
    pygame.display.flip()
    return button_rect, None


def draw_configure_screen():
    screen.fill((255, 255, 255))
    input_rects = {}
    
    # Title/Keyboard name at the top
    keyboard_name_rect = pygame.Rect(30, 15, 150, 20)
    color = (100, 100, 255) if active_input == "keyboard_name" else (200, 200, 200)
    pygame.draw.rect(screen, color, keyboard_name_rect)
    pygame.draw.rect(screen, (0, 0, 0), keyboard_name_rect, 1)
    display_name = label_text if active_input == "keyboard_name" else (keyboard_name_text or selected_keyboard["name"])
    text = font.render(display_name, True, (0, 0, 0))
    screen.blit(text, (keyboard_name_rect.x + 5, keyboard_name_rect.y + 3))
    input_rects["keyboard_name"] = keyboard_name_rect

    # Draw keyboard area (shifted down)
    keyboard_area_start_y = 50  # Increased Y position for keyboard area
    text_rects = []
    for key in current_keys:
        color = (100, 100, 255) if key == dragged_key or key == configuring_key else (200, 200, 200)
        key_rect = pygame.Rect(key["x"], key["y"] + keyboard_area_start_y, key["width"], key["height"])
        pygame.draw.rect(screen, color, key_rect)
        pygame.draw.rect(screen, (0, 0, 0), key_rect, 1)
        text = font.render(key["char"], True, (0, 0, 0))
        text_rect = text.get_rect(center=(key["x"] + key["width"] // 2, key["y"] + keyboard_area_start_y + key["height"] // 2))
        screen.blit(text, text_rect)
        text_rects.append(text_rect)

        # Draw swipe direction/action labels for every key (like in use mode)
        for direction in DIRECTIONS[1:]:
            action_text = key["actions"][direction]
            if not action_text:
                continue
            font_size = 10
            temp_font = small_font
            temp_text = temp_font.render(action_text, True, (0, 0, 0))
            if temp_text.get_width() > 80:
                font_size = max(6, int(10 * 80 / temp_text.get_width()))
                temp_font = pygame.font.SysFont("arial", font_size)
                temp_text = temp_font.render(action_text, True, (0, 0, 0))
            text = temp_text

            # Positioning logic copied from draw_keyboard
            if direction == "Up":
                base_pos = (key["x"] + key["width"] // 2, key["y"] + keyboard_area_start_y - 8)
                text_rect = text.get_rect(center=base_pos)
                offset_dir = (0, -1)
            elif direction == "Down":
                base_pos = (key["x"] + key["width"] // 2, key["y"] + keyboard_area_start_y + key["height"] + 8)
                text_rect = text.get_rect(center=base_pos)
                offset_dir = (0, 1)
            elif direction == "Left":
                base_pos = (key["x"] - 4, key["y"] + keyboard_area_start_y + key["height"] // 2)
                text_rect = text.get_rect(midright=base_pos)
                offset_dir = (-1, 0)
            elif direction == "Right":
                base_pos = (key["x"] + key["width"] + 4, key["y"] + keyboard_area_start_y + key["height"] // 2)
                text_rect = text.get_rect(midleft=base_pos)
                offset_dir = (1, 0)
            elif direction == "Up-Left":
                base_pos = (key["x"] - 4, key["y"] + keyboard_area_start_y - 4)
                text_rect = text.get_rect(bottomright=base_pos)
                offset_dir = (-1, -1)
            elif direction == "Up-Right":
                base_pos = (key["x"] + key["width"] + 4, key["y"] + keyboard_area_start_y - 4)
                text_rect = text.get_rect(bottomleft=base_pos)
                offset_dir = (1, -1)
            elif direction == "Down-Left":
                base_pos = (key["x"] - 4, key["y"] + keyboard_area_start_y + key["height"] + 4)
                text_rect = text.get_rect(topright=base_pos)
                offset_dir = (-1, 1)
            elif direction == "Down-Right":
                base_pos = (key["x"] + key["width"] + 4, key["y"] + keyboard_area_start_y + key["height"] + 4)
                text_rect = text.get_rect(topleft=base_pos)
                offset_dir = (1, 1)

            offset = 0
            max_offset = 50
            while offset < max_offset:
                collides = False
                for other_rect in text_rects:
                    if text_rect.colliderect(other_rect):
                        collides = True
                        break
                if not collides:
                    break
                offset += 5
                new_x = base_pos[0] + offset * offset_dir[0]
                new_y = base_pos[1] + offset * offset_dir[1]
                if direction in ["Up", "Down"]:
                    text_rect = text.get_rect(center=(new_x, new_y))
                elif direction == "Left":
                    text_rect = text.get_rect(midright=(new_x, new_y))
                elif direction == "Right":
                    text_rect = text.get_rect(midleft=(new_x, new_y))
                elif direction == "Up-Left":
                    text_rect = text.get_rect(bottomright=(new_x, new_y))
                elif direction == "Up-Right":
                    text_rect = text.get_rect(bottomleft=(new_x, new_y))
                elif direction == "Down-Left":
                    text_rect = text.get_rect(topright=(new_x, new_y))
                elif direction == "Down-Right":
                    text_rect = text.get_rect(topleft=(new_x, new_y))

            screen.blit(text, text_rect)
            text_rects.append(text_rect)

    # Configuration panel on the right
    config_panel_x = screen.get_width() - 250  # Always 250px from the right edge
    config_panel_y = 50
   
    if configuring_key:
        # Draw swipe direction configuration
        for i, direction in enumerate(DIRECTIONS):
            y = config_panel_y + i * 25  # Increased spacing between items
            text = font.render(f"{direction}:", True, (0, 0, 0))
            screen.blit(text, (config_panel_x, y))
            action_rect = pygame.Rect(config_panel_x + 100, y, 118, 20)
            color = (100, 100, 255) if active_input == direction else (200, 200, 200)
            pygame.draw.rect(screen, color, action_rect)
            pygame.draw.rect(screen, (0, 0, 0), action_rect, 1)
            action_text = label_text if active_input == direction else action_texts.get(direction, configuring_key["actions"][direction])
            text = small_font.render(action_text, True, (0, 0, 0))
            text_rect = text.get_rect(x=action_rect.x + 5, y=action_rect.y + 3)
            if text_rect.width > 113:
                text = small_font.render(action_text[:int(113 / (text_rect.width / len(action_text)))], True, (0, 0, 0))
            screen.blit(text, (action_rect.x + 5, action_rect.y + 3))
            input_rects[direction] = action_rect
           
            up_arrow_rect = pygame.Rect(action_rect.right + 4, y, 10, 10)
            down_arrow_rect = pygame.Rect(action_rect.right + 4, y + 10, 10, 10)
            up_color = (100, 100, 255) if up_arrow_rect.collidepoint(pygame.mouse.get_pos()) else (200, 200, 200)
            down_color = (100, 100, 255) if down_arrow_rect.collidepoint(pygame.mouse.get_pos()) else (200, 200, 200)
            pygame.draw.polygon(screen, up_color, [(up_arrow_rect.x, up_arrow_rect.bottom), (up_arrow_rect.centerx, up_arrow_rect.top), (up_arrow_rect.right, up_arrow_rect.bottom)])
            pygame.draw.polygon(screen, down_color, [(down_arrow_rect.x, down_arrow_rect.top), (down_arrow_rect.centerx, down_arrow_rect.bottom), (down_arrow_rect.right, down_arrow_rect.top)])
            input_rects[f"{direction}_up_arrow"] = up_arrow_rect
            input_rects[f"{direction}_down_arrow"] = down_arrow_rect
       
        # Width and height configuration (below swipe directions)
        dimension_y = config_panel_y + len(DIRECTIONS) * 25 + 10
       
        width_rect = pygame.Rect(config_panel_x + 100, dimension_y, 120, 20)
        color = (100, 100, 255) if active_input == "width" else (200, 200, 200)
        pygame.draw.rect(screen, color, width_rect)
        pygame.draw.rect(screen, (0, 0, 0), width_rect, 1)
        width_text = label_text if active_input == "width" else (str(configuring_key["width"]) if configuring_key else "40")
        text = font.render("Width: " + width_text, True, (0, 0, 0))
        screen.blit(text, (config_panel_x, dimension_y))
        input_rects["width"] = width_rect
       
        height_rect = pygame.Rect(config_panel_x + 100, dimension_y + 25, 120, 20)
        color = (100, 100, 255) if active_input == "height" else (200, 200, 200)
        pygame.draw.rect(screen, color, height_rect)
        pygame.draw.rect(screen, (0, 0, 0), height_rect, 1)
        height_text = label_text if active_input == "height" else (str(configuring_key["height"]) if configuring_key else "40")
        text = font.render("Height: " + height_text, True, (0, 0, 0))
        screen.blit(text, (config_panel_x, dimension_y + 25))
        input_rects["height"] = height_rect
    else:
        text = font.render("No key selected", True, (255, 0, 0))
        screen.blit(text, (config_panel_x, config_panel_y))
   
    # Bottom buttons
    add_key_button = pygame.Rect(30, 365, 100, 20)
    pygame.draw.rect(screen, (100, 100, 255), add_key_button)
    pygame.draw.rect(screen, (0, 0, 0), add_key_button, 1)
    text = font.render("Add Key", True, (0, 0, 0))
    text_rect = text.get_rect(center=add_key_button.center)
    screen.blit(text, text_rect)
   
    done_button = pygame.Rect(150, 365, 100, 20)
    pygame.draw.rect(screen, (255, 100, 100), done_button)
    pygame.draw.rect(screen, (0, 0, 0), done_button, 1)
    text = font.render("Done", True, (0, 0, 0))
    text_rect = text.get_rect(center=done_button.center)
    screen.blit(text, text_rect)
   
    delete_key_button = pygame.Rect(270, 365, 100, 20)
    pygame.draw.rect(screen, (255, 50, 50), delete_key_button)
    pygame.draw.rect(screen, (0, 0, 0), delete_key_button, 1)
    text = font.render("Delete Key", True, (0, 0, 0))
    text_rect = text.get_rect(center=delete_key_button.center)
    screen.blit(text, text_rect)
   
    pygame.display.flip()
    return add_key_button, done_button, delete_key_button, input_rects


def draw_keyboard_list():
    global scroll_offset, max_scroll
    screen.fill((255, 255, 255))
    keyboard_buttons = []
    item_height = 60
    canvas_height = 400
    mouse_pos = pygame.mouse.get_pos()
   
    # Calculate max scroll
    max_scroll = max(0, item_height * len(keyboards) - canvas_height + 60)
    scroll_offset = max(0, min(scroll_offset, max_scroll))
   
    for i in range(len(keyboards)):
        y = 40 + i * item_height - scroll_offset
        if y < -40 or y > canvas_height:
            continue
        select_button = pygame.Rect(40, y, 220, 40)
        color = (100, 100, 255) if select_button.collidepoint(mouse_pos) else (200, 200, 200)
        pygame.draw.rect(screen, color, select_button)
        outline_color = (0, 0, 0)  # Changed to always be black
        pygame.draw.rect(screen, outline_color, select_button, 2)
        text = font.render(keyboards[i]["name"], True, (0, 0, 0))
        text_rect = text.get_rect(center=select_button.center)
        screen.blit(text, text_rect)
       
        edit_button = pygame.Rect(260, y, 60, 40)
        color = (100, 100, 255) if edit_button.collidepoint(mouse_pos) else (200, 200, 200)
        pygame.draw.rect(screen, color, edit_button)
        pygame.draw.rect(screen, outline_color, edit_button, 2)
        text = font.render("Edit", True, (0, 0, 0))
        text_rect = text.get_rect(center=edit_button.center)
        screen.blit(text, text_rect)
       
        delete_button = pygame.Rect(330, y, 80, 40)
        color = (100, 100, 255) if delete_button.collidepoint(mouse_pos) else (200, 200, 200)
        pygame.draw.rect(screen, color, delete_button)
        pygame.draw.rect(screen, outline_color, delete_button, 2)
        text = font.render("Delete", True, (0, 0, 0))
        text_rect = text.get_rect(center=delete_button.center)
        screen.blit(text, text_rect)
       
        keyboard_buttons.append((select_button, edit_button, delete_button, i))
   
    # Load input
    load_input_rect = pygame.Rect(40, 300, 410, 40)
    color = (100, 100, 255) if active_input == "load_code" else (200, 200, 200)
    pygame.draw.rect(screen, color, load_input_rect)
    pygame.draw.rect(screen, (0, 0, 0), load_input_rect, 1)
    display_text = label_text if active_input == "load_code" else (load_code_text or "Paste JSON code here")
    text = small_font.render(display_text[:50], True, (0, 0, 0))  # Truncate for display
    screen.blit(text, (load_input_rect.x + 5, load_input_rect.y + 12))
   
    # Buttons
    save_button_rect = pygame.Rect(40, 350, 80, 40)
    color = (100, 100, 255) if save_button_rect.collidepoint(mouse_pos) else (200, 200, 200)
    pygame.draw.rect(screen, color, save_button_rect)
    pygame.draw.rect(screen, (0, 0, 0), save_button_rect, 1)
    text = font.render("Save", True, (0, 0, 0))
    text_rect = text.get_rect(center=save_button_rect.center)
    screen.blit(text, text_rect)
   
    load_button_rect = pygame.Rect(130, 350, 80, 40)
    color = (100, 100, 255) if load_button_rect.collidepoint(mouse_pos) else (200, 200, 200)
    pygame.draw.rect(screen, color, load_button_rect)
    pygame.draw.rect(screen, (0, 0, 0), load_button_rect, 1)
    text = font.render("Load", True, (0, 0, 0))
    text_rect = text.get_rect(center=load_button_rect.center)
    screen.blit(text, text_rect)
   
    add_button_rect = pygame.Rect(220, 350, 150, 40)
    color = (100, 100, 255) if add_button_rect.collidepoint(mouse_pos) else (200, 200, 200)
    pygame.draw.rect(screen, color, add_button_rect)
    pygame.draw.rect(screen, (0, 0, 0), add_button_rect, 1)
    text = font.render("Add Keyboard", True, (0, 0, 0))
    text_rect = text.get_rect(center=add_button_rect.center)
    screen.blit(text, text_rect)
   
    pygame.display.flip()
    return add_button_rect, save_button_rect, load_button_rect, load_input_rect, keyboard_buttons, None


def draw_keyboard():
    screen.fill((255, 255, 255))
    if selected_keyboard:
        text_rects = []
        for key in selected_keyboard["keys"]:
            color = (100, 100, 255) if key == selected_key else (200, 200, 200)
            key_rect = pygame.Rect(key["x"], key["y"], key["width"], key["height"])
            pygame.draw.rect(screen, color, key_rect)
            pygame.draw.rect(screen, (0, 0, 0), key_rect, 1)
            text = font.render(key["char"], True, (0, 0, 0))
            text_rect = text.get_rect(center=(key["x"] + key["width"] // 2, key["y"] + key["height"] // 2))
            screen.blit(text, text_rect)
            text_rects.append(text_rect)
           
            for direction in DIRECTIONS[1:]:
                action_text = key["actions"][direction]
                if not action_text:
                    continue
                font_size = 10
                temp_font = small_font
                temp_text = temp_font.render(action_text, True, (0, 0, 0))
                if temp_text.get_width() > 80:
                    font_size = max(6, int(10 * 80 / temp_text.get_width()))
                    temp_font = pygame.font.SysFont("arial", font_size)
                    temp_text = temp_font.render(action_text, True, (0, 0, 0))
                text = temp_text
               
                if direction == "Up":
                    base_pos = (key["x"] + key["width"] // 2, key["y"] - 8)
                    text_rect = text.get_rect(center=base_pos)
                    offset_dir = (0, -1)
                elif direction == "Down":
                    base_pos = (key["x"] + key["width"] // 2, key["y"] + key["height"] + 8)
                    text_rect = text.get_rect(center=base_pos)
                    offset_dir = (0, 1)
                elif direction == "Left":
                    base_pos = (key["x"] - 4, key["y"] + key["height"] // 2)
                    text_rect = text.get_rect(midright=base_pos)
                    offset_dir = (-1, 0)
                elif direction == "Right":
                    base_pos = (key["x"] + key["width"] + 4, key["y"] + key["height"] // 2)
                    text_rect = text.get_rect(midleft=base_pos)
                    offset_dir = (1, 0)
                elif direction == "Up-Left":
                    base_pos = (key["x"] - 4, key["y"] - 4)
                    text_rect = text.get_rect(bottomright=base_pos)
                    offset_dir = (-1, -1)
                elif direction == "Up-Right":
                    base_pos = (key["x"] + key["width"] + 4, key["y"] - 4)
                    text_rect = text.get_rect(bottomleft=base_pos)
                    offset_dir = (1, -1)
                elif direction == "Down-Left":
                    base_pos = (key["x"] - 4, key["y"] + key["height"] + 4)
                    text_rect = text.get_rect(topright=base_pos)
                    offset_dir = (-1, 1)
                elif direction == "Down-Right":
                    base_pos = (key["x"] + key["width"] + 4, key["y"] + key["height"] + 4)
                    text_rect = text.get_rect(topleft=base_pos)
                    offset_dir = (1, 1)
               
                offset = 0
                max_offset = 50
                while offset < max_offset:
                    collides = False
                    for other_rect in text_rects:
                        if text_rect.colliderect(other_rect):
                            collides = True
                            break
                    if not collides:
                        break
                    offset += 5
                    new_x = base_pos[0] + offset * offset_dir[0]
                    new_y = base_pos[1] + offset * offset_dir[1]
                    if direction in ["Up", "Down"]:
                        text_rect = text.get_rect(center=(new_x, new_y))
                    elif direction == "Left":
                        text_rect = text.get_rect(midright=(new_x, new_y))
                    elif direction == "Right":
                        text_rect = text.get_rect(midleft=(new_x, new_y))
                    elif direction == "Up-Left":
                        text_rect = text.get_rect(bottomright=(new_x, new_y))
                    elif direction == "Up-Right":
                        text_rect = text.get_rect(bottomleft=(new_x, new_y))
                    elif direction == "Down-Left":
                        text_rect = text.get_rect(topright=(new_x, new_y))
                    elif direction == "Down-Right":
                        text_rect = text.get_rect(topleft=(new_x, new_y))
               
                screen.blit(text, text_rect)
                text_rects.append(text_rect)
       
        if input_buffer:
            text = font.render(f"Buffer: {input_buffer}", True, (0, 0, 0))
            screen.blit(text, (30, 330))
        if last_typed_text:
            text = font.render(f"Last: {last_typed_text}", True, (0, 0, 0))
            screen.blit(text, (30, 350))
       
        back_button_rect = pygame.Rect(650, 365, 100, 20)
        pygame.draw.rect(screen, (255, 100, 100), back_button_rect)
        pygame.draw.rect(screen, (0, 0, 0), back_button_rect, 1)
        text = font.render("Back", True, (0, 0, 0))
        text_rect = text.get_rect(center=back_button_rect.center)
        screen.blit(text, text_rect)
   
    pygame.display.flip()
    return back_button_rect


def get_swipe_direction(start_pos, end_pos):
    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    angle = math.degrees(math.atan2(dy, dx)) % 360
    if 22.5 <= angle < 67.5:
        return "Down-Right"
    elif 67.5 <= angle < 112.5:
        return "Down"
    elif 112.5 <= angle < 157.5:
        return "Down-Left"
    elif 157.5 <= angle < 202.5:
        return "Left"
    elif 202.5 <= angle < 247.5:
        return "Up-Left"
    elif 247.5 <= angle < 292.5:
        return "Up"
    elif 292.5 <= angle < 337.5:
        return "Up-Right"
    else:
        return "Right"


def update_loop():
    global state, selected_key, swipe_start, swipe_direction, selected_keyboard, current_keys, dragged_key, configuring_key, label_text, text_active, active_input, action_texts, scroll_offset, dragged_scroll, keyboard_name_text, last_typed_text, input_buffer, show_keyboard, last_arrow_click, scroll_start_y, keyboards, load_code_text, screen
   
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            return
        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
           
            if state == "start":
                button_rect, _ = draw_start_screen()
                if button_rect.collidepoint(mouse_pos):
                    selected_keyboard = create_default_keyboard()
                    current_keys = selected_keyboard["keys"]
                    configuring_key = current_keys[0] if current_keys else None
                    label_text = ""
                    keyboard_name_text = selected_keyboard["name"]
                    action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS} if configuring_key else {}
                    state = "configure"
           
            elif state == "configure" and selected_keyboard:
                add_key_button, done_button, delete_key_button, input_rects = draw_configure_screen()
                if add_key_button.collidepoint(mouse_pos):
                    last_key = configuring_key or current_keys[-1] if current_keys else None
                    new_key = create_new_key(last_key)
                    current_keys.append(new_key)
                    configuring_key = new_key
                    label_text = ""
                    action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS}
                    text_active = False
                    active_input = None
                    dragged_key = None
                elif done_button.collidepoint(mouse_pos):
                    selected_keyboard["keys"] = current_keys
                    selected_keyboard["name"] = keyboard_name_text if keyboard_name_text.strip() else "Unnamed Keyboard"
                    if selected_keyboard["keys"]:
                        found = False
                        for i, kb in enumerate(keyboards):
                            if kb["id"] == selected_keyboard["id"]:
                                keyboards[i] = selected_keyboard
                                found = True
                                break
                        if not found:
                            keyboards.append(selected_keyboard)
                    state = "list"
                    selected_keyboard = None
                    current_keys = []
                    configuring_key = None
                    dragged_key = None
                    label_text = ""
                    keyboard_name_text = ""
                    action_texts = {}
                    text_active = False
                    active_input = None
                elif delete_key_button.collidepoint(mouse_pos):
                    if configuring_key:
                        current_keys.remove(configuring_key)
                        configuring_key = current_keys[0] if current_keys else None
                        label_text = ""
                        action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS} if configuring_key else {}
                        text_active = False
                        active_input = None
                        dragged_key = None
                else:
                    text_active = False
                    active_input = None
                    for input_name, rect in input_rects.items():
                        if rect.collidepoint(mouse_pos):
                            if "_up_arrow" in input_name or "_down_arrow" in input_name:
                                if configuring_key and time.time() - last_arrow_click > 0.1:
                                    last_arrow_click = time.time()
                                    direction = input_name.split("_")[0]
                                    current_text = action_texts.get(direction, configuring_key["actions"][direction])
                                    current_index = 0
                                    for i, key in enumerate(SPECIAL_KEYS):
                                        if key == current_text:
                                            current_index = i
                                            break
                                    if "_up_arrow" in input_name:
                                        new_index = (current_index + 1) % len(SPECIAL_KEYS)
                                    else:
                                        new_index = (current_index - 1) % len(SPECIAL_KEYS)
                                    new_text = SPECIAL_KEYS[new_index]
                                    action_texts[direction] = new_text
                                    configuring_key["actions"][direction] = new_text
                                    if direction == "Tap":
                                        configuring_key["char"] = new_text if new_text.strip() else "Key"
                            else:
                                text_active = True
                                active_input = input_name
                                if input_name == "keyboard_name":
                                    label_text = keyboard_name_text
                                elif input_name in ["width", "height"]:
                                    label_text = str(configuring_key[input_name]) if configuring_key else "40"
                                elif configuring_key:
                                    label_text = action_texts.get(input_name, configuring_key["actions"][input_name])
                            break
                    else:
                        keyboard_area_start_y = 50  # Add this line to define the offset
                        for key in current_keys:
                            if (key["x"] <= mouse_pos[0] <= key["x"] + key["width"] and
                                key["y"] + keyboard_area_start_y <= mouse_pos[1] <= key["y"] + keyboard_area_start_y + key["height"]):
                                dragged_key = key
                                configuring_key = key
                                label_text = ""
                                action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS}
                                text_active = False
                                active_input = None
                                break
           
            elif state == "list":
                add_button_rect, save_button_rect, load_button_rect, load_input_rect, keyboard_buttons, scrollbar_rect = draw_keyboard_list()
                delete_indices = []
               
                clicked_button = False
                for select_button, edit_button, delete_button, idx in keyboard_buttons:
                    select_collision_rect = pygame.Rect(select_button.x, select_button.y + scroll_offset, select_button.width, select_button.height)
                    edit_collision_rect = pygame.Rect(edit_button.x, edit_button.y + scroll_offset, edit_button.width, edit_button.height)
                    delete_collision_rect = pygame.Rect(delete_button.x, delete_button.y + scroll_offset, delete_button.width, delete_button.height)
                   
                    try:
                        if select_collision_rect.collidepoint(mouse_pos):
                            if idx < len(keyboards):
                                selected_keyboard = keyboards[idx]
                                state = "keyboard"
                                selected_key = None
                                swipe_start = None
                                swipe_direction = None
                                last_typed_text = ""
                                show_keyboard = True
                                clicked_button = True
                        elif edit_collision_rect.collidepoint(mouse_pos):
                            if idx < len(keyboards):
                                selected_keyboard = keyboards[idx]
                                current_keys = copy.deepcopy(selected_keyboard["keys"]) or [create_new_key()]
                                configuring_key = current_keys[0] if current_keys else None
                                label_text = ""
                                keyboard_name_text = selected_keyboard["name"]
                                action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS} if configuring_key else {}
                                state = "configure"
                                clicked_button = True
                        elif delete_collision_rect.collidepoint(mouse_pos):
                            if idx < len(keyboards):
                                delete_indices.append(idx)
                                clicked_button = True
                    except IndexError:
                        continue
               
                for idx in sorted(delete_indices, reverse=True):
                    try:
                        if idx < len(keyboards):
                            keyboards.pop(idx)
                            draw_keyboard_list()
                    except IndexError:
                        continue
               
                if add_button_rect.collidepoint(mouse_pos):
                    selected_keyboard = create_default_keyboard()
                    current_keys = selected_keyboard["keys"]
                    configuring_key = current_keys[0] if current_keys else None
                    label_text = ""
                    keyboard_name_text = selected_keyboard["name"]
                    action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS} if configuring_key else {}
                    state = "configure"
                    clicked_button = True
                elif save_button_rect.collidepoint(mouse_pos):
                    try:
                        json_str = json.dumps(keyboards, indent=2)
                        copy_to_clipboard(json_str)
                        print("Keyboard configuration copied to clipboard")
                    except Exception as e:
                        print(f"Save error: {e}")
                    clicked_button = True
                elif load_button_rect.collidepoint(mouse_pos):
                    try:
                        clipboard_text = get_clipboard_text()
                        if clipboard_text.strip():
                            try:
                                new_keyboards = json.loads(clipboard_text)
                                if isinstance(new_keyboards, list) and all(isinstance(kb, dict) and "id" in kb and "name" in kb and "keys" in kb for kb in new_keyboards):
                                    keyboards = new_keyboards
                                    scroll_offset = 0
                                    print("Keyboard configuration loaded from clipboard")
                                else:
                                    print("Invalid JSON: Not a list of keyboards")
                            except json.JSONDecodeError as e:
                                print(f"JSON parse error: {e}")
                        else:
                            print("No JSON code in clipboard")
                    except Exception as e:
                        print(f"Load error: {e}")
                    clicked_button = True
                elif load_input_rect.collidepoint(mouse_pos):
                    text_active = True
                    active_input = "load_code"
                    label_text = load_code_text
                    clicked_button = True
               
                if not clicked_button and len(keyboards) > 6:
                    dragged_scroll = True
                    scroll_start_y = mouse_pos[1]
           
            elif state == "keyboard" and selected_keyboard:
                back_button_rect = draw_keyboard()
                if back_button_rect.collidepoint(mouse_pos):
                    state = "list"
                    selected_keyboard = None
                    selected_key = None
                    swipe_start = None
                    swipe_direction = None
                    last_typed_text = ""
                    show_keyboard = False
                else:
                    for key in selected_keyboard["keys"]:
                        if (key["x"] <= mouse_pos[0] <= key["x"] + key["width"] and
                            key["y"] <= mouse_pos[1] <= key["y"] + key["height"]):
                            selected_key = key
                            swipe_start = mouse_pos
                            swipe_direction = None
                            break
       
        elif event.type == pygame.MOUSEBUTTONUP:
            if state == "configure":
                dragged_key = None
            elif state == "keyboard" and selected_key and swipe_start:
                mouse_pos = event.pos
                dist = math.hypot(mouse_pos[0] - swipe_start[0], mouse_pos[1] - swipe_start[1])
                if dist > 20:
                    swipe_direction = get_swipe_direction(swipe_start, mouse_pos)
                else:
                    swipe_direction = "Tap"
                action_text = selected_key["actions"][swipe_direction]
                if action_text.strip():
                    send_key(action_text)
                    last_typed_text = action_text
                selected_key = None
                swipe_start = None
                swipe_direction = None
            elif state == "list":
                dragged_scroll = False
       
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = event.pos
            if state == "configure" and dragged_key:
                keyboard_area_start_y = 50  # Add this line to define the offset
                dragged_key["x"] = max(0, min(mouse_pos[0] - dragged_key["width"] // 2, 800 - dragged_key["width"]))
                dragged_key["y"] = max(0, min(mouse_pos[1] - keyboard_area_start_y - dragged_key["height"] // 2, 360 - dragged_key["height"]))
            elif state == "keyboard" and selected_key:
                dist = math.hypot(mouse_pos[0] - swipe_start[0], mouse_pos[1] - swipe_start[1])
                if dist > 20:
                    swipe_direction = get_swipe_direction(swipe_start, mouse_pos)
            elif state == "list" and dragged_scroll:
                delta_y = scroll_start_y - mouse_pos[1]
                scroll_offset = max(0, min(scroll_offset + delta_y, max_scroll))
                scroll_start_y = mouse_pos[1]
       
        elif event.type == pygame.KEYDOWN and text_active and active_input:
            # Handle clipboard shortcuts in text boxes
            if event.key == pygame.K_c and (event.mod & pygame.KMOD_CTRL):
                copy_to_clipboard(label_text)
            elif event.key == pygame.K_x and (event.mod & pygame.KMOD_CTRL):
                copy_to_clipboard(label_text)
                label_text = ""
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                try:
                    pasted = get_clipboard_text()
                    if pasted:
                        label_text += pasted
                except Exception as e:
                    print(f"Paste error: {e}")
            elif event.key == pygame.K_a and (event.mod & pygame.KMOD_CTRL):
                copy_to_clipboard(label_text)
            elif event.key == pygame.K_RETURN:
                if active_input == "keyboard_name":
                    keyboard_name_text = label_text if label_text.strip() else "Unnamed Keyboard"
                elif configuring_key and active_input in DIRECTIONS:
                    configuring_key["actions"][active_input] = label_text
                    action_texts[active_input] = configuring_key["actions"][active_input]
                    if active_input == "Tap":
                        configuring_key["char"] = label_text if label_text.strip() else "Key"
                elif configuring_key and active_input in ["width", "height"]:
                    try:
                        value = int(label_text) if label_text.strip() else 40
                        value = max(20, min(200, value))
                        configuring_key[active_input] = value
                    except ValueError:
                        configuring_key[active_input] = 40
                elif active_input == "load_code":
                    load_code_text = label_text
                    try:
                        if load_code_text.strip():
                            new_keyboards = json.loads(load_code_text)
                            if isinstance(new_keyboards, list) and all(isinstance(kb, dict) and "id" in kb and "name" in kb and "keys" in kb for kb in new_keyboards):
                                keyboards = new_keyboards
                                scroll_offset = 0
                            else:
                                print("Invalid JSON: Not a list of keyboards")
                        else:
                            print("No JSON code to load")
                    except json.JSONDecodeError as e:
                        print(f"JSON parse error: {e}")
                    except Exception as e:
                        print(f"Load error: {e}")
                text_active = False
                active_input = None
                label_text = ""
            elif event.key == pygame.K_BACKSPACE:
                label_text = label_text[:-1]
            elif event.unicode.isprintable():
                if active_input in ["width", "height"]:
                    if event.unicode.isdigit():
                        label_text += event.unicode
                else:
                    label_text += event.unicode
   
    if state == "start":
        draw_start_screen()
    elif state == "configure":
        draw_configure_screen()
    elif state == "list":
        draw_keyboard_list()
    elif state == "keyboard":
        draw_keyboard()


FPS = 60


async def main():
    setup()
    while True:
        try:
            update_loop()
            await asyncio.sleep(1.0 / FPS)
        except Exception as e:
            error_msg = f"Main loop error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            break


if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pygame.quit()


