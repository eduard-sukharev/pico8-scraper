from pathlib import Path


def check_mouse_usage(cart_path: Path) -> bool:
    from pico8_decoder import extract_code

    lua_code = extract_code(str(cart_path))
    if not lua_code:
        return False

    lua_code_lower = lua_code.lower()

    has_mouse = False
    for stat_num in range(30, 34):
        stat_str = f"stat({stat_num})"
        if stat_str in lua_code_lower:
            has_mouse = True
            break

    if not has_mouse:
        return False

    has_dpad = "btn(" in lua_code_lower or "btnp(" in lua_code_lower

    return not has_dpad
