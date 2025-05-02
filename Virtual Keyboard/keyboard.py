import pygame
import asyncio
import platform
import math
import uuid
import copy
import time
import traceback
import json

# Import ctypes for Windows API calls
if platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOPMOST = 0x00000008

# Import for macOS window level (requires pyobjc)
if platform.system() == "Darwin":
    try:
        from AppKit import NSWindow, NSFloatingWindowLevel, NSNonactivatingPanelMask
        import objc
    except ImportError:
        print("Warning: pyobjc not installed. Always-on-top and non-activating may not work on macOS.")
        objc = None

try:
    import pyperclip
except ImportError:
    print("Warning: pyperclip not installed. Clipboard functionality may be limited.")
    pyperclip = None

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05
except ImportError:
    print("Warning: pyautogui not installed. Typing may be limited.")
    pyautogui = None

try:
    import keyboard
except ImportError:
    print("Warning: keyboard not installed. Falling back to pyautogui.")
    keyboard = None

js = None

def setup():
    global screen, font, small_font, tiny_font, state, keyboards, selected_key, swipe_start, swipe_direction, selected_keyboard, current_keys, dragged_key, configuring_key, label_text, text_active, active_input, action_texts, scroll_offset, max_scroll, dragged_scroll, keyboard_name_text, last_typed_text, SPECIAL_KEYS, last_arrow_click, input_buffer, show_keyboard, scroll_start_y, load_code_text, active_modifiers, caps_lock_active, feedback_message, feedback_timer, last_key_action_time
    pygame.display.init()
    pygame.font.init()
    pygame.event.set_allowed([pygame.QUIT, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.KEYDOWN, pygame.VIDEORESIZE])
    
    info = pygame.display.Info()
    screen_width = info.current_w
    screen_height = info.current_h
    window_width = int(screen_width * 0.9)
    window_height = int(screen_height * 0.9)
    window_x = (screen_width - window_width) // 2
    window_y = (screen_height - window_height) // 2
    
    # Use NOFRAME to avoid focus-taking borders; rely on RESIZABLE for basic window management
    screen = pygame.display.set_mode((window_width, window_height), pygame.RESIZABLE | pygame.NOFRAME)
    pygame.display.set_caption("Virtual Touchscreen Keyboard")
    
    hwnd = pygame.display.get_wm_info()['window']
    if platform.system() == "Windows":
        # Set window to be always on top and non-activating
        user32.SetWindowPos(hwnd, -1, window_x, window_y, window_width, window_height, 0x0001 | 0x0002)
        user32.SetWindowLongW(hwnd, -20, user32.GetWindowLongW(hwnd, -20) | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
    elif platform.system() == "Linux":
        try:
            import Xlib.display
            display = Xlib.display.Display()
            window = display.create_resource_object('window', hwnd)
            atom = display.intern_atom('_NET_WM_STATE_ABOVE')
            window.change_property(display.intern_atom('_NET_WM_STATE'), Xlib.Xatom.ATOM, 32, [atom])
            # Set input hint to prevent focus
            window.set_wm_hints(flags=Xlib.Xutil.InputHint, input=False)
            window.configure(x=window_x, y=window_y, width=window_width, height=window_height)
            display.sync()
        except Exception as e:
            print(f"Linux: Failed to set window position or non-activating: {e}")
    elif platform.system() == "Darwin" and objc:
        try:
            ns_window = objc.objc_object(ptr=hwnd)
            ns_window.setLevel_(NSFloatingWindowLevel)
            ns_window.setStyleMask_(NSNonactivatingPanelMask)
            ns_window.setFrameOrigin_((window_x, screen_height - window_y - window_height))
            ns_window.setContentSize_((window_width, window_height))
        except Exception as e:
            print(f"macOS: Failed to set window position or non-activating: {e}")
    
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
    active_modifiers = {"Shift": False, "Ctrl": False, "Alt": False, "Tab": False, "Windows": False}
    caps_lock_active = False
    feedback_message = ""
    feedback_timer = 0
    last_key_action_time = 0
    SPECIAL_KEYS = [
        "", "Shift", "Ctrl", "Alt", "Tab", "Enter", "Backspace", "Space",
        "Esc", "Delete", "CapsLock", "Windows", "Up", "Down", "Left", "Right"
    ]
    last_arrow_click = 0

DIRECTIONS = ["Tap", "Up", "Down", "Left", "Right", "Up-Left", "Up-Right", "Down-Left", "Down-Right"]

def set_feedback_message(message, duration=2.0):
    global feedback_message, feedback_timer
    feedback_message = message
    feedback_timer = time.time() + duration
    print(f"Feedback set: {message}")

def restore_target_focus():
    """Ensure the target application is focused before typing or showing keyboard."""
    if pyautogui:
        try:
            print("Restoring focus to target application")
            pyautogui.click()  # Simulate a click to focus the active window
            time.sleep(0.1)  # Brief pause to ensure focus
        except Exception as e:
            print(f"Failed to restore focus: {e}")

def copy_to_clipboard(text):
    try:
        if not text:
            print("Clipboard write failed: Empty text")
            return False
        if platform.system() == "Emscripten":
            if js is None:
                print("Clipboard write failed: js module not available")
                return False
            try:
                escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                js_code = f'''
                    navigator.clipboard.writeText("{escaped_text}")
                        .then(() => console.log("Clipboard write success"))
                        .catch(err => console.error("Clipboard write error: " + err));
                '''
                js.eval(js_code)
                print("Clipboard write attempted in Emscripten")
                return True
            except Exception as e:
                print(f"Clipboard write failed in Emscripten: {e}")
                return False
        else:
            if pyperclip is None:
                print("Clipboard write failed: pyperclip not installed")
                return False
            pyperclip.copy(text)
            print(f"Clipboard write success: {text[:50]}...")
            return True
    except Exception as e:
        print(f"Clipboard write failed: {e}\n{traceback.format_exc()}")
        return False

def get_clipboard_text():
    try:
        if platform.system() == "Emscripten":
            if js is None:
                print("Clipboard read failed: js module not available")
                return ""
            try:
                js_code = '''
                    navigator.clipboard.readText()
                        .then(text => text)
                        .catch(err => { console.error("Clipboard read error: " + err); return ""; })
                '''
                text = js.eval(js_code)
                print(f"Clipboard read in Emscripten: {text[:50]}..." if text else "Clipboard read empty")
                return text or ""
            except Exception as e:
                print(f"Clipboard read failed in Emscripten: {e}")
                return ""
        else:
            if pyperclip is None:
                print("Clipboard read failed: pyperclip not installed")
                return ""
            text = pyperclip.paste()
            print(f"Clipboard read success: {text[:50]}..." if text else "Clipboard read empty")
            return text or ""
    except Exception as e:
        print(f"Clipboard read failed: {e}\n{traceback.format_exc()}")
        return ""

def truncate_text(text, font, max_width):
    if not text:
        return text
    text_width = font.size(text)[0]
    if text_width <= max_width:
        return text
    ellipsis = "..."
    ellipsis_width = font.size(ellipsis)[0]
    available_width = max_width - ellipsis_width
    if available_width <= 0:
        return ellipsis
    truncated = ""
    for i in range(len(text)):
        if font.size(text[:i+1])[0] > available_width:
            break
        truncated = text[:i+1]
    return truncated + ellipsis

def send_key(text):
    global input_buffer, active_modifiers, caps_lock_active, last_typed_text
    
    if not text:
        print("send_key: No text provided")
        set_feedback_message("No text to type")
        return
    
    print(f"send_key called with text: '{text}' on {platform.system()}")
    
    # Handle CapsLock toggle
    if text == "CapsLock":
        caps_lock_active = not caps_lock_active
        set_feedback_message("Caps Lock " + ("On" if caps_lock_active else "Off"))
        print("Caps Lock toggled")
        active_modifiers = {key: False for key in active_modifiers}
        return
    
    # Handle modifiers
    if text in ["Shift", "Ctrl", "Alt", "Tab", "Windows"]:
        active_modifiers[text] = True
        set_feedback_message(f"{text} pressed")
        print(f"Modifier {text} set to True")
        return
    
    try:
        if platform.system() == "Emscripten":
            # Browser environment: Simulate key events via JavaScript
            key_map = {
                "Enter": {"key": "Enter", "code": "Enter", "keyCode": 13},
                "Backspace": {"key": "Backspace", "code": "Backspace", "keyCode": 8},
                "Space": {"key": " ", "code": "Space", "keyCode": 32},
                "Tab": {"key": "Tab", "code": "Tab", "keyCode": 9},
                "Esc": {"key": "Escape", "code": "Escape", "keyCode": 27},
                "Delete": {"key": "Delete", "code": "Delete", "keyCode": 46},
                "Up": {"key": "ArrowUp", "code": "ArrowUp", "keyCode": 38},
                "Down": {"key": "ArrowDown", "code": "ArrowDown", "keyCode": 40},
                "Left": {"key": "ArrowLeft", "code": "ArrowLeft", "keyCode": 37},
                "Right": {"key": "ArrowRight", "code": "ArrowRight", "keyCode": 39}
            }
            
            text_to_send = text.upper() if active_modifiers["Shift"] or caps_lock_active else text
            props = key_map.get(text, {
                "key": text_to_send,
                "code": f"Key{text_to_send.upper()}" if len(text_to_send) == 1 else "",
                "keyCode": ord(text_to_send.upper()) if len(text_to_send) == 1 else 0
            })
            props["shiftKey"] = active_modifiers["Shift"]
            props["ctrlKey"] = active_modifiers["Ctrl"]
            props["altKey"] = active_modifiers["Alt"]
            
            # Ensure browser focus is on the target input field
            restore_target_focus()
            
            js_code = f'''
            let el = document.activeElement;
            if (!el || (el.tagName !== "INPUT" && el.tagName !== "TEXTAREA" && !el.isContentEditable)) {{
                el = document.querySelector("input, textarea, [contenteditable]") || document.body;
                if (el) el.focus();
            }}
            if (el) {{
                let eventProps = {{
                    key: "{props['key']}",
                    code: "{props.get('code', '')}",
                    keyCode: {props.get('keyCode', 0)},
                    shiftKey: {str(props.get('shiftKey', False)).lower()},
                    ctrlKey: {str(props.get('ctrlKey', False)).lower()},
                    altKey: {str(props.get('altKey', False)).lower()},
                    bubbles: true,
                    cancelable: true
                }};
                ["keydown", "keypress", "keyup"].forEach(eventType => {{
                    el.dispatchEvent(new KeyboardEvent(eventType, eventProps));
                }});
                if ("{text}" === "Backspace") {{
                    let start = el.selectionStart;
                    if (start > 0) {{
                        el.value = el.value.substring(0, start - 1) + el.value.substring(start);
                        el.selectionStart = el.selectionEnd = start - 1;
                    }}
                }} else if ("{text}" === "Delete") {{
                    let start = el.selectionStart;
                    el.value = el.value.substring(0, start) + el.value.substring(start + 1);
                    el.selectionStart = el.selectionEnd = start;
                }} else if ("{text}" === "Space") {{
                    let start = el.selectionStart;
                    el.value = el.value.substring(0, start) + " " + el.value.substring(start);
                    el.selectionStart = el.selectionEnd = start + 1;
                }} else if ("{text}" === "Enter") {{
                    let start = el.selectionStart;
                    el.value = el.value.substring(0, start) + "\\n" + el.value.substring(start);
                    el.selectionStart = el.selectionEnd = start + 1;
                }} else if ("{text}" !== "Shift" && "{text}" !== "Ctrl" && "{text}" !== "Alt" && "{text}" !== "Tab" && "{text}" !== "Windows") {{
                    let start = el.selectionStart;
                    el.value = el.value.substring(0, start) + "{props['key']}" + el.value.substring(start);
                    el.selectionStart = el.selectionEnd = start + "{props['key']}".length;
                }}
            }} else {{
                console.error("No focusable element found");
            }}
            '''
            js.eval(js_code)
            set_feedback_message(f"Typed: {text_to_send}")
            last_typed_text = text_to_send
            print(f"Emscripten: Typed '{text_to_send}' to browser")
        else:
            # Desktop environment: Use pyautogui or keyboard
            if pyautogui is None and keyboard is None:
                set_feedback_message("Typing failed: Install pyautogui or keyboard")
                print("No typing method available")
                return
            
            # Ensure target is focused
            restore_target_focus()
            
            key_map = {
                "Backspace": "backspace",
                "Space": "space",
                "Enter": "enter",
                "Tab": "tab",
                "Delete": "delete",
                "Esc": "esc",
                "Up": "up",
                "Down": "down",
                "Left": "left",
                "Right": "right",
                "Windows": "win"
            }
            
            text_to_send = text.upper() if active_modifiers["Shift"] or caps_lock_active else text
            if pyautogui:
                print(f"Using pyautogui to type '{text_to_send}'")
                if text in key_map:
                    pyautogui.press(key_map[text])
                    print(f"Pressed special key: {key_map[text]}")
                elif active_modifiers["Ctrl"] and text.lower() in ["c", "v", "x", "a", "z"]:
                    pyautogui.hotkey("ctrl", text.lower())
                    print(f"Hotkey: ctrl+{text.lower()}")
                else:
                    pyautogui.write(text_to_send, interval=0.05)
                    print(f"Typed: {text_to_send}")
            elif keyboard:
                print(f"Using keyboard library to type '{text_to_send}'")
                if text in key_map:
                    keyboard.press_and_release(key_map[text])
                    print(f"Pressed special key: {key_map[text]}")
                elif active_modifiers["Ctrl"] and text.lower() in ["c", "v", "x", "a", "z"]:
                    keyboard.press_and_release(f"ctrl+{text.lower()}")
                    print(f"Hotkey: ctrl+{text.lower()}")
                else:
                    keyboard.write(text_to_send)
                    print(f"Typed: {text_to_send}")
            
            set_feedback_message(f"Typed: {text_to_send}")
            last_typed_text = text_to_send
            input_buffer += text_to_send
            print(f"Success: Typed '{text_to_send}' on {platform.system()}")
        
        # Reset modifiers after typing
        active_modifiers = {key: False for key in active_modifiers}
        print("Modifiers reset")
    
    except Exception as e:
        error_msg = f"Typing error: {str(e)}"
        set_feedback_message(error_msg)
        print(f"Typing error ({platform.system()}): {error_msg}\n{traceback.format_exc()}")
        input_buffer += text

def create_default_keyboard():
    keyboard = create_new_keyboard()
    keyboard["name"] = ""
    keyboard["keys"] = []
    return keyboard

def create_new_keyboard():
    keyboard_id = str(uuid.uuid4())
    return {"id": keyboard_id, "name": "", "keys": []}

def create_new_key(last_key=None):
    actions = {direction: "" for direction in DIRECTIONS}
    return {"char": "", "x": 40, "y": 40, "width": 40, "height": 40, "actions": actions}

def draw_start_screen():
    screen.fill((255, 255, 255))
    screen_width = screen.get_width()
    screen_height = screen.get_height()
    start_screen_height = int(0.3 * screen_height)
    start_screen_y = screen_height - start_screen_height
    start_screen_rect = pygame.Rect(0, start_screen_y, screen_width, start_screen_height)
    pygame.draw.rect(screen, (240, 240, 240), start_screen_rect)
    
    add_button_rect = pygame.Rect(20, start_screen_y + 20, 100, 40)
    save_button_rect = pygame.Rect(130, start_screen_y + 20, 100, 40)
    load_button_rect = pygame.Rect(240, start_screen_y + 20, 100, 40)
    paste_input_rect = pygame.Rect(350, start_screen_y + 20, 180, 40)
    delete_code_button_rect = pygame.Rect(540, start_screen_y + 20, 120, 40)
    help_button_rect = pygame.Rect(670, start_screen_y + 20, 40, 40)
    
    for rect, text in [
        (add_button_rect, "Add Keyboard"),
        (save_button_rect, "Save"),
        (load_button_rect, "Load"),
        (delete_code_button_rect, "Delete All Code"),
        (help_button_rect, "?")
    ]:
        color = (100, 100, 255) if rect.collidepoint(pygame.mouse.get_pos()) else (200, 200, 200)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (0, 0, 0), rect, 1)
        text_surf = font.render(text, True, (0, 0, 0))
        text_rect = text_surf.get_rect(center=rect.center)
        screen.blit(text_surf, text_rect)
    
    color = (100, 100, 255) if active_input == "start_load_code" else (200, 200, 200)
    pygame.draw.rect(screen, color, paste_input_rect)
    pygame.draw.rect(screen, (0, 0, 0), paste_input_rect, 1)
    display_text = label_text if active_input == "start_load_code" else (load_code_text or "Paste JSON code here")
    display_text = truncate_text(display_text, small_font, paste_input_rect.width - 10)
    text_surf = small_font.render(display_text, True, (0, 0, 0))
    screen.blit(text_surf, (paste_input_rect.x + 5, paste_input_rect.y + 12))
    
    if feedback_message and time.time() < feedback_timer:
        text_surf = font.render(feedback_message, True, (255, 0, 0))
        screen.blit(text_surf, (20, start_screen_y - 20))
    
    pygame.display.flip()
    return add_button_rect, save_button_rect, load_button_rect, paste_input_rect, delete_code_button_rect, help_button_rect

def draw_help_screen():
    global scroll_offset, max_scroll
    screen.fill((255, 255, 255))
    canvas_width = screen.get_width() - 40
    canvas_height = screen.get_height() - 100
    line_height = 20
    margin = 20
    mouse_pos = pygame.mouse.get_pos()
    
    help_text = [
        "How to Use the Virtual Touchscreen Keyboard",
        "",
        "This application lets you create, configure, and use a virtual touchscreen keyboard to type into applications like Google Docs, websites, or system fields (e.g., Windows search bar).",
        "",
        "1. Start Screen:",
        "- 'Add Keyboard': Click to create a new keyboard layout.",
        "- 'Save': Copies the current keyboard's JSON data to your clipboard.",
        "- 'Load': Pastes JSON data from the clipboard to load a saved keyboard.",
        "- 'Paste JSON code here': Click to paste JSON data for loading.",
        "- 'Delete All Code': Clears the JSON input field.",
        "- '?': Shows this help guide.",
        "",
        "2. Creating a Keyboard:",
        "- Click 'Add Keyboard' to enter the configuration screen.",
        "- Name your keyboard by clicking the name field and typing.",
        "- Click 'Add Key' to create a new key (starts blank).",
        "- Drag keys to position them on the left side of the screen.",
        "- Select a key to configure it on the right panel.",
        "",
        "3. Configuring Keys:",
        "- 'Tap', 'Up', 'Down', etc.: Set actions for each gesture.",
        "  - Click a field to type a character (e.g., 'a') or special key (e.g., 'Enter').",
        "  - Use up/down arrows to cycle through special keys (Shift, Ctrl, etc.).",
        "  - 'Tap' sets the key's display character.",
        "- 'Width' and 'Height': Adjust key size (20-200 pixels).",
        "- 'Delete Key': Removes the selected key.",
        "- 'Done': Saves the keyboard and returns to the keyboard list.",
        "",
        "4. Special Keys:",
        "- Supported: Shift, Ctrl, Alt, Tab, Windows, CapsLock, Enter, Backspace, Space, Esc, Delete, Up, Down, Left, Right.",
        "- Modifiers (Shift, Ctrl, etc.) turn blue when active.",
        "- CapsLock toggles uppercase; other modifiers reset after a non-modifier key.",
        "",
        "5. Keyboard List:",
        "- Shows all saved keyboards.",
        "- 'Select': Use a keyboard for typing.",
        "- 'Edit': Modify a keyboard's layout.",
        "- 'Delete': Remove a keyboard.",
        "- 'Add Keyboard', 'Save', 'Load', 'Delete All Code': Same as start screen.",
        "- Scroll by dragging if there are many keyboards.",
        "",
        "6. Typing with the Keyboard:",
        "- Select a keyboard from the list to enter typing mode.",
        "- Click a key to perform its 'Tap' action (e.g., type 'a').",
        "- Swipe in a direction (Up, Down, etc.) for other actions.",
        "- Keys type into the active application, website, or system field.",
        "- Ensure the target (e.g., Google Docs, Windows search bar) is focused before typing.",
        "- Key actions have a 0.2-second cooldown to prevent repeats.",
        "- The keyboard stays on top and doesn't take focus, so typing goes to the target.",
        "- 'Back': Return to the keyboard list.",
        "",
        "7. Typing in Google Docs or Websites:",
        "- Open the website (e.g., Google Docs in Chrome).",
        "- Click into the text field to focus it.",
        "- Use the virtual keyboard to type letters, numbers, or special keys.",
        "- Examples: 'Enter' adds a new line, 'Tab' moves focus, 'Ctrl+C' copies text.",
        "- Shift or CapsLock for uppercase; Ctrl for shortcuts (e.g., Ctrl+V).",
        "",
        "8. Typing in System Fields (e.g., Windows Search):",
        "- Click the search bar or press Win key to focus it.",
        "- Use the keyboard to type (e.g., 'hi' to search for 'hi').",
        "- Special keys like 'Enter' or 'Tab' work as expected.",
        "",
        "9. Saving and Loading:",
        "- 'Save': Copies the keyboard's JSON to the clipboard.",
        "- Paste the JSON into the 'Paste JSON code here' field and click 'Load'.",
        "- JSON includes the keyboard name and key configurations.",
        "",
        "10. Troubleshooting:",
        "- Install dependencies: Run 'pip install pygame pyperclip pyautogui keyboard' (and 'pyobjc' for macOS).",
        "- ALSA/XDG errors: Set 'SDL_AUDIODRIVER=directsound' or disable audio.",
        "- Typing fails: Ensure the target is focused; try clicking it first.",
        "- JSON errors: Check for valid format (must have 'name' and 'keys').",
        "- Errors: Check the console for details; ensure all libraries are installed.",
        "",
        "Need extra help or have ideas? Contact 2424lplp@gmail.com. May take a while to respond, be patient."
    ]
    
    total_height = len(help_text) * line_height
    max_scroll = max(0, total_height - canvas_height + 60)
    scroll_offset = max(0, min(scroll_offset, max_scroll))
    
    for i, line in enumerate(help_text):
        y = margin + i * line_height - scroll_offset
        if y < -line_height or y > canvas_height:
            continue
        text_surf = small_font.render(line, True, (0, 0, 0))
        screen.blit(text_surf, (margin, y))
    
    back_button_rect = pygame.Rect(screen.get_width() - 120, screen.get_height() - 60, 100, 40)
    color = (255, 100, 100) if back_button_rect.collidepoint(mouse_pos) else (200, 200, 200)
    pygame.draw.rect(screen, color, back_button_rect)
    pygame.draw.rect(screen, (0, 0, 0), back_button_rect, 1)
    text_surf = font.render("Back", True, (0, 0, 0))
    text_rect = text_surf.get_rect(center=back_button_rect.center)
    screen.blit(text_surf, text_rect)
    
    if feedback_message and time.time() < feedback_timer:
        text_surf = font.render(feedback_message, True, (255, 0, 0))
        screen.blit(text_surf, (margin, canvas_height + 20))
    
    pygame.display.flip()
    return back_button_rect

def draw_configure_screen():
    screen.fill((255, 255, 255))
    input_rects = {}
    
    keyboard_name_rect = pygame.Rect(30, 15, 150, 20)
    color = (100, 100, 255) if active_input == "keyboard_name" else (200, 200, 200)
    pygame.draw.rect(screen, color, keyboard_name_rect)
    pygame.draw.rect(screen, (0, 0, 0), keyboard_name_rect, 1)
    display_name = label_text if active_input == "keyboard_name" else (keyboard_name_text or selected_keyboard["name"])
    display_name = truncate_text(display_name, font, keyboard_name_rect.width - 10)
    text = font.render(display_name, True, (0, 0, 0))
    screen.blit(text, (keyboard_name_rect.x + 5, keyboard_name_rect.y + 3))
    input_rects["keyboard_name"] = keyboard_name_rect

    keyboard_area_start_y = 50
    text_rects = []
    modifier_keys = ["Shift", "Ctrl", "Alt", "Tab", "Windows", "CapsLock"]
    for key in current_keys:
        color = (100, 100, 255) if key == dragged_key or key == configuring_key else (200, 200, 200)
        key_rect = pygame.Rect(key["x"], key["y"] + keyboard_area_start_y, key["width"], key["height"])
        pygame.draw.rect(screen, color, key_rect)
        pygame.draw.rect(screen, (0, 0, 0), key_rect, 1)
        key_label = key["char"] or " "
        text_color = (0, 0, 255) if key_label in modifier_keys and (active_modifiers.get(key_label, False) or (key_label == "CapsLock" and caps_lock_active)) else (0, 0, 0)
        text = font.render(key_label, True, text_color)
        text_rect = text.get_rect(center=(key["x"] + key["width"] // 2, key["y"] + keyboard_area_start_y + key["height"] // 2))
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

    config_panel_x = screen.get_width() - 250
    config_panel_y = 50
    
    if configuring_key:
        for i, direction in enumerate(DIRECTIONS):
            y = config_panel_y + i * 25
            text = font.render(f"{direction}:", True, (0, 0, 0))
            screen.blit(text, (config_panel_x, y))
            action_rect = pygame.Rect(config_panel_x + 100, y, 118, 20)
            color = (100, 100, 255) if active_input == direction else (200, 200, 200)
            pygame.draw.rect(screen, color, action_rect)
            pygame.draw.rect(screen, (0, 0, 0), action_rect, 1)
            action_text = label_text if active_input == direction else action_texts.get(direction, configuring_key["actions"][direction])
            action_text = truncate_text(action_text, small_font, action_rect.width - 10)
            text = small_font.render(action_text, True, (0, 0, 0))
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
        
        dimension_y = config_panel_y + len(DIRECTIONS) * 25 + 10
        
        width_rect = pygame.Rect(config_panel_x + 100, dimension_y, 120, 20)
        color = (100, 100, 255) if active_input == "width" else (200, 200, 200)
        pygame.draw.rect(screen, color, width_rect)
        pygame.draw.rect(screen, (0, 0, 0), width_rect, 1)
        width_text = label_text if active_input == "width" else (str(configuring_key["width"]) if configuring_key else "40")
        width_text = truncate_text(width_text, font, width_rect.width - 10)
        text = font.render("Width: " + width_text, True, (0, 0, 0))
        screen.blit(text, (config_panel_x, dimension_y))
        input_rects["width"] = width_rect
        
        height_rect = pygame.Rect(config_panel_x + 100, dimension_y + 25, 120, 20)
        color = (100, 100, 255) if active_input == "height" else (200, 200, 200)
        pygame.draw.rect(screen, color, height_rect)
        pygame.draw.rect(screen, (0, 0, 0), height_rect, 1)
        height_text = label_text if active_input == "height" else (str(configuring_key["height"]) if configuring_key else "40")
        height_text = truncate_text(height_text, font, height_rect.width - 10)
        text = font.render("Height: " + height_text, True, (0, 0, 0))
        screen.blit(text, (config_panel_x, dimension_y + 25))
        input_rects["height"] = height_rect
    else:
        text = font.render("No key selected", True, (255, 0, 0))
        screen.blit(text, (config_panel_x, config_panel_y))
    
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
    
    max_scroll = max(0, item_height * len(keyboards) - canvas_height + 60)
    scroll_offset = max(0, min(scroll_offset, max_scroll))
    
    for i in range(len(keyboards)):
        y = 40 + i * item_height - scroll_offset
        if y < -40 or y > canvas_height:
            continue
        select_button = pygame.Rect(40, y, 220, 40)
        color = (100, 100, 255) if select_button.collidepoint(mouse_pos) else (200, 200, 200)
        pygame.draw.rect(screen, color, select_button)
        outline_color = (0, 0, 0)
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
    
    load_input_rect = pygame.Rect(40, 300, 410, 40)
    color = (100, 100, 255) if active_input == "load_code" else (200, 200, 200)
    pygame.draw.rect(screen, color, load_input_rect)
    pygame.draw.rect(screen, (0, 0, 0), load_input_rect, 1)
    display_text = label_text if active_input == "load_code" else (load_code_text or "Paste JSON code here")
    display_text = truncate_text(display_text, small_font, load_input_rect.width - 10)
    text = small_font.render(display_text, True, (0, 0, 0))
    screen.blit(text, (load_input_rect.x + 5, load_input_rect.y + 12))
    
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
    
    delete_code_button_rect = pygame.Rect(380, 350, 120, 40)
    color = (100, 100, 255) if delete_code_button_rect.collidepoint(mouse_pos) else (200, 200, 200)
    pygame.draw.rect(screen, color, delete_code_button_rect)
    pygame.draw.rect(screen, (0, 0, 0), delete_code_button_rect, 1)
    text = font.render("Delete All Code", True, (0, 0, 0))
    text_rect = text.get_rect(center=delete_code_button_rect.center)
    screen.blit(text, text_rect)
    
    if feedback_message and time.time() < feedback_timer:
        text_surf = font.render(feedback_message, True, (255, 0, 0))
        screen.blit(text_surf, (40, 280))
    
    pygame.display.flip()
    return add_button_rect, save_button_rect, load_button_rect, load_input_rect, keyboard_buttons, None, delete_code_button_rect

def draw_keyboard():
    screen.fill((255, 255, 255))
    if selected_keyboard:
        text_rects = []
        modifier_keys = ["Shift", "Ctrl", "Alt", "Tab", "Windows", "CapsLock"]
        for key in selected_keyboard["keys"]:
            color = (100, 100, 255) if key == selected_key else (200, 200, 200)
            key_rect = pygame.Rect(key["x"], key["y"], key["width"], key["height"])
            pygame.draw.rect(screen, color, key_rect)
            pygame.draw.rect(screen, (0, 0, 0), key_rect, 1)
            key_label = key["char"] or " "
            text_color = (0, 0, 255) if key_label in modifier_keys and (active_modifiers.get(key_label, False) or (key_label == "CapsLock" and caps_lock_active)) else (0, 0, 0)
            text = font.render(key_label, True, text_color)
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
    global state, selected_key, swipe_start, swipe_direction, selected_keyboard, current_keys, dragged_key, configuring_key, label_text, text_active, active_input, action_texts, scroll_offset, dragged_scroll, keyboard_name_text, last_typed_text, input_buffer, show_keyboard, last_arrow_click, scroll_start_y, keyboards, load_code_text, screen, feedback_message, feedback_timer, last_key_action_time
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            return
        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE | pygame.NOFRAME)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif text_active and active_input:
                try:
                    if event.key == pygame.K_c and (event.mod & pygame.KMOD_CTRL):
                        if copy_to_clipboard(label_text):
                            set_feedback_message("Text copied")
                            print(f"Copied text to clipboard: {label_text[:50]}...")
                    elif event.key == pygame.K_x and (event.mod & pygame.KMOD_CTRL):
                        if copy_to_clipboard(label_text):
                            label_text = ""
                            set_feedback_message("Text cut")
                            print("Cut text to clipboard")
                    elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                        pasted = get_clipboard_text()
                        if pasted:
                            label_text += pasted
                            set_feedback_message("Text pasted")
                            print(f"Pasted text: {pasted[:50]}...")
                            if active_input in ["start_load_code", "load_code"]:
                                load_code_text = label_text
                    elif event.key == pygame.K_a and (event.mod & pygame.KMOD_CTRL):
                        if copy_to_clipboard(label_text):
                            set_feedback_message("Text selected")
                            print("Selected and copied all text")
                    elif event.key == pygame.K_RETURN:
                        if active_input in ["start_load_code", "load_code"]:
                            load_code_text = label_text
                            text_active = False
                            active_input = None
                            label_text = ""
                            set_feedback_message("JSON code set")
                            print(f"JSON code set from paste box ({active_input})")
                        elif active_input == "keyboard_name":
                            keyboard_name_text = label_text if label_text.strip() else ""
                        elif configuring_key and active_input in DIRECTIONS:
                            configuring_key["actions"][active_input] = label_text
                            action_texts[active_input] = configuring_key["actions"][active_input]
                            if active_input == "Tap":
                                configuring_key["char"] = label_text
                        elif configuring_key and active_input in ["width", "height"]:
                            try:
                                value = int(label_text) if label_text.strip() else 40
                                value = max(20, min(200, value))
                                configuring_key[active_input] = value
                            except ValueError:
                                configuring_key[active_input] = 40
                    elif event.key == pygame.K_BACKSPACE:
                        label_text = label_text[:-1]
                        if active_input in ["start_load_code", "load_code"]:
                            load_code_text = label_text
                    elif event.unicode.isprintable():
                        if active_input in ["width", "height"]:
                            if event.unicode.isdigit():
                                label_text += event.unicode
                        else:
                            label_text += event.unicode
                            if active_input in ["start_load_code", "load_code"]:
                                load_code_text = label_text
                except Exception as e:
                    set_feedback_message("Key error")
                    print(f"Key event error: {e}\n{traceback.format_exc()}")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            try:
                if state == "start":
                    add_button_rect, save_button_rect, load_button_rect, paste_input_rect, delete_code_button_rect, help_button_rect = draw_start_screen()
                    if add_button_rect.collidepoint(mouse_pos):
                        selected_keyboard = create_default_keyboard()
                        current_keys = selected_keyboard["keys"]
                        configuring_key = current_keys[0] if current_keys else None
                        label_text = ""
                        keyboard_name_text = selected_keyboard["name"]
                        action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS} if configuring_key else {}
                        state = "configure"
                        set_feedback_message("New keyboard created")
                        print("Add Keyboard button clicked")
                    elif save_button_rect.collidepoint(mouse_pos):
                        print("Save button clicked (start)")
                        try:
                            if not keyboards:
                                set_feedback_message("No keyboards to save")
                                print("No keyboards to save")
                            else:
                                kb_to_save = selected_keyboard if selected_keyboard else keyboards[0]
                                json_data = {"name": kb_to_save["name"], "keys": kb_to_save["keys"]}
                                json_str = json.dumps(json_data, indent=2)
                                print(f"Generated JSON: {json_str[:100]}...")
                                if copy_to_clipboard(json_str):
                                    set_feedback_message("Keyboard JSON copied")
                                    print("JSON copied to clipboard")
                                else:
                                    set_feedback_message("Copy failed")
                                    print("Failed to copy JSON to clipboard")
                        except Exception as e:
                            set_feedback_message("Save error")
                            print(f"Save error: {e}\n{traceback.format_exc()}")
                    elif load_button_rect.collidepoint(mouse_pos):
                        print("Load button clicked (start)")
                        try:
                            if load_code_text and load_code_text.strip():
                                new_keyboard = json.loads(load_code_text)
                                if not isinstance(new_keyboard, dict):
                                    set_feedback_message("Invalid JSON: Must be an object")
                                    print("Invalid JSON: Not an object")
                                elif "name" not in new_keyboard or "keys" not in new_keyboard:
                                    set_feedback_message("Invalid JSON: Missing 'name' or 'keys'")
                                    print("Invalid JSON: Missing required fields")
                                elif not isinstance(new_keyboard["keys"], list):
                                    set_feedback_message("Invalid JSON: 'keys' must be a list")
                                    print("Invalid JSON: 'keys' not a list")
                                else:
                                    new_keyboard["id"] = str(uuid.uuid4())
                                    keyboards.append(new_keyboard)
                                    state = "list"
                                    set_feedback_message("Keyboard loaded")
                                    print("Keyboard loaded from JSON")
                            else:
                                set_feedback_message("No JSON to load")
                                print("No JSON code provided")
                        except json.JSONDecodeError as e:
                            set_feedback_message(f"JSON parse error: {str(e)}")
                            print(f"JSON parse error: {e}\n{traceback.format_exc()}")
                        except Exception as e:
                            set_feedback_message("Load error")
                            print(f"Load error: {e}\n{traceback.format_exc()}")
                    elif paste_input_rect.collidepoint(mouse_pos):
                        text_active = True
                        active_input = "start_load_code"
                        label_text = load_code_text or ""
                        set_feedback_message("Paste box activated")
                        print("Paste JSON input activated (start)")
                    elif delete_code_button_rect.collidepoint(mouse_pos):
                        load_code_text = ""
                        label_text = ""
                        text_active = False
                        active_input = None
                        set_feedback_message("Paste input cleared")
                        print("Delete All Code button clicked (start)")
                    elif help_button_rect.collidepoint(mouse_pos):
                        state = "help"
                        scroll_offset = 0
                        set_feedback_message("Help guide opened")
                        print("Help button clicked")
                
                elif state == "help":
                    back_button_rect = draw_help_screen()
                    if back_button_rect.collidepoint(mouse_pos):
                        state = "start"
                        scroll_offset = 0
                        set_feedback_message("Returned to start screen")
                        print("Back from help screen")
                    else:
                        dragged_scroll = True
                        scroll_start_y = mouse_pos[1]
                
                elif state == "configure" and selected_keyboard:
                    add_key_button, done_button, delete_key_button, input_rects = draw_configure_screen()
                    if add_key_button.collidepoint(mouse_pos):
                        new_key = create_new_key()
                        current_keys.append(new_key)
                        configuring_key = new_key
                        label_text = ""
                        action_texts = {direction: "" for direction in DIRECTIONS}
                        text_active = False
                        active_input = None
                        dragged_key = None
                        print("Added new blank key")
                    elif done_button.collidepoint(mouse_pos):
                        selected_keyboard["keys"] = current_keys
                        selected_keyboard["name"] = keyboard_name_text
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
                        print("Saved keyboard and returned to list")
                    elif delete_key_button.collidepoint(mouse_pos):
                        if configuring_key:
                            current_keys.remove(configuring_key)
                            configuring_key = current_keys[0] if current_keys else None
                            label_text = ""
                            action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS} if configuring_key else {}
                            text_active = False
                            active_input = None
                            dragged_key = None
                            print("Deleted key")
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
                                            configuring_key["char"] = new_text
                                        print(f"Changed {direction} to '{new_text}'")
                                else:
                                    text_active = True
                                    active_input = input_name
                                    if input_name == "keyboard_name":
                                        label_text = keyboard_name_text
                                    elif input_name in ["width", "height"]:
                                        label_text = str(configuring_key[input_name]) if configuring_key else "40"
                                    elif configuring_key:
                                        label_text = action_texts.get(input_name, configuring_key["actions"][input_name])
                                    print(f"Activated input: {input_name}")
                                break
                        else:
                            keyboard_area_start_y = 50
                            for key in current_keys:
                                if (key["x"] <= mouse_pos[0] <= key["x"] + key["width"] and
                                    key["y"] + keyboard_area_start_y <= mouse_pos[1] <= key["y"] + keyboard_area_start_y + key["height"]):
                                    dragged_key = key
                                    configuring_key = key
                                    label_text = ""
                                    action_texts = {direction: configuring_key["actions"][direction] for direction in DIRECTIONS}
                                    text_active = False
                                    active_input = None
                                    print(f"Selected key with char: {key['char']}")
                                    break
                
                elif state == "list":
                    add_button_rect, save_button_rect, load_button_rect, load_input_rect, keyboard_buttons, scrollbar_rect, delete_code_button_rect = draw_keyboard_list()
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
                                    restore_target_focus()  # Restore focus to target application
                                    clicked_button = True
                                    print(f"Selected keyboard: {selected_keyboard['name']}")
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
                                    print(f"Editing keyboard: {selected_keyboard['name']}")
                            elif delete_collision_rect.collidepoint(mouse_pos):
                                if idx < len(keyboards):
                                    delete_indices.append(idx)
                                    clicked_button = True
                                    print(f"Deleted keyboard at index {idx}")
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
                        print("Add Keyboard button clicked")
                    elif save_button_rect.collidepoint(mouse_pos):
                        print("Save button clicked (list)")
                        try:
                            if not keyboards:
                                set_feedback_message("No keyboards to save")
                                print("No keyboards to save")
                            else:
                                kb_to_save = selected_keyboard if selected_keyboard else keyboards[0]
                                json_data = {"name": kb_to_save["name"], "keys": kb_to_save["keys"]}
                                json_str = json.dumps(json_data, indent=2)
                                print(f"Generated JSON: {json_str[:100]}...")
                                if copy_to_clipboard(json_str):
                                    set_feedback_message("Keyboard JSON copied")
                                    print("JSON copied to clipboard")
                                else:
                                    set_feedback_message("Copy failed")
                                    print("Failed to copy JSON to clipboard")
                        except Exception as e:
                            set_feedback_message("Save error")
                            print(f"Save error: {e}\n{traceback.format_exc()}")
                        clicked_button = True
                    elif load_button_rect.collidepoint(mouse_pos):
                        print("Load button clicked (list)")
                        try:
                            if load_code_text and load_code_text.strip():
                                new_keyboard = json.loads(load_code_text)
                                if not isinstance(new_keyboard, dict):
                                    set_feedback_message("Invalid JSON: Must be an object")
                                    print("Invalid JSON: Not an object")
                                elif "name" not in new_keyboard or "keys" not in new_keyboard:
                                    set_feedback_message("Invalid JSON: Missing 'name' or 'keys'")
                                    print("Invalid JSON: Missing required fields")
                                elif not isinstance(new_keyboard["keys"], list):
                                    set_feedback_message("Invalid JSON: 'keys' must be a list")
                                    print("Invalid JSON: 'keys' not a list")
                                else:
                                    new_keyboard["id"] = str(uuid.uuid4())
                                    keyboards.append(new_keyboard)
                                    scroll_offset = 0
                                    set_feedback_message("Keyboard loaded")
                                    print("Keyboard loaded from JSON")
                            else:
                                set_feedback_message("No JSON to load")
                                print("No JSON code provided")
                        except json.JSONDecodeError as e:
                            set_feedback_message(f"JSON parse error: {str(e)}")
                            print(f"JSON parse error: {e}\n{traceback.format_exc()}")
                        except Exception as e:
                            set_feedback_message("Load error")
                            print(f"Load error: {e}\n{traceback.format_exc()}")
                        clicked_button = True
                    elif load_input_rect.collidepoint(mouse_pos):
                        text_active = True
                        active_input = "load_code"
                        label_text = load_code_text or ""
                        set_feedback_message("Paste box activated")
                        print("Paste JSON input activated (list)")
                        clicked_button = True
                    elif delete_code_button_rect.collidepoint(mouse_pos):
                        load_code_text = ""
                        label_text = ""
                        text_active = False
                        active_input = None
                        set_feedback_message("Paste input cleared")
                        print("Delete All Code button clicked (list)")
                        clicked_button = True
                    elif not clicked_button:
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
                        input_buffer = ""
                        last_typed_text = ""
                        active_modifiers = {key: False for key in active_modifiers}
                        caps_lock_active = False
                        restore_target_focus()  # Restore focus when exiting keyboard
                        print("Back to keyboard list")
                    else:
                        for key in selected_keyboard["keys"]:
                            if (key["x"] <= mouse_pos[0] <= key["x"] + key["width"] and
                                key["y"] <= mouse_pos[1] <= key["y"] + key["height"]):
                                selected_key = key
                                swipe_start = mouse_pos
                                swipe_direction = None
                                print(f"Selected key for swipe: {key['char']}")
                                break
            except Exception as e:
                set_feedback_message("Mouse down error")
                print(f"Mouse down error: {e}\n{traceback.format_exc()}")
        
        elif event.type == pygame.MOUSEBUTTONUP:
            try:
                if state == "keyboard" and selected_key and swipe_start:
                    mouse_pos = event.pos
                    current_time = time.time()
                    if current_time - last_key_action_time < 0.2:
                        print("Key action ignored: Within cooldown")
                        selected_key = None
                        swipe_start = None
                        swipe_direction = None
                        continue
                    swipe_direction = get_swipe_direction(swipe_start, mouse_pos)
                    dx = mouse_pos[0] - swipe_start[0]
                    dy = mouse_pos[1] - swipe_start[1]
                    distance = math.sqrt(dx**2 + dy**2)
                    if distance < 10:
                        swipe_direction = "Tap"
                    action_text = selected_key["actions"].get(swipe_direction, "")
                    if action_text:
                        send_key(action_text)
                        last_key_action_time = current_time
                        print(f"Performed {swipe_direction} action: '{action_text}'")
                    else:
                        print(f"No action defined for {swipe_direction}")
                    selected_key = None
                    swipe_start = None
                    swipe_direction = None
                dragged_key = None
                dragged_scroll = False
            except Exception as e:
                set_feedback_message("Mouse up error")
                print(f"Mouse up error: {e}\n{traceback.format_exc()}")
        
        elif event.type == pygame.MOUSEMOTION:
            try:
                mouse_pos = event.pos
                if dragged_key and state == "configure":
                    keyboard_area_start_y = 50
                    dragged_key["x"] = max(0, min(mouse_pos[0] - dragged_key["width"] // 2, screen.get_width() - 250 - dragged_key["width"]))
                    dragged_key["y"] = max(0, min(mouse_pos[1] - keyboard_area_start_y - dragged_key["height"] // 2, screen.get_height() - keyboard_area_start_y - dragged_key["height"]))
                elif dragged_scroll:
                    delta_y = scroll_start_y - mouse_pos[1]
                    scroll_offset = max(0, min(scroll_offset + delta_y, max_scroll))
                    scroll_start_y = mouse_pos[1]
            except Exception as e:
                set_feedback_message("Mouse motion error")
                print(f"Mouse motion error: {e}\n{traceback.format_exc()}")

async def main():
    setup()  # Initialize pygame and window settings
    FPS = 60
    try:
        while True:
            if state == "start":
                draw_start_screen()
            elif state == "help":
                draw_help_screen()
            elif state == "configure":
                draw_configure_screen()
            elif state == "list":
                draw_keyboard_list()
            elif state == "keyboard":
                if show_keyboard:
                    draw_keyboard()
            update_loop()
            await asyncio.sleep(1.0 / FPS)  # Control frame rate
    except KeyboardInterrupt:
        pygame.quit()

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())
