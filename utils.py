from typing import Any, Dict, Optional, Tuple



def extract_message_fields(msg: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str], Optional[float], Optional[float]]:
    """
    Returns: (msg_type, text_body, media_id, latitude, longitude)
    """
    msg_type = msg.get("type")
    list_msg_id = None
    button_msg_id = None
    text_body = None
    media_id = None
    latitude = longitude = None

    if msg_type == "text":
        text_body = msg.get("text", {}).get("body")

    elif msg_type == "button":
        text_body = msg.get("button", {}).get("text")

    elif msg_type == "interactive":
        interactive = msg.get("interactive", {})
        if interactive.get("type") == "button_reply":
            msg_type = "interactive_button_reply"
            button_msg_id = interactive.get("button_reply", {}).get("id")  # e.g. role_driver1
            text_body = interactive.get("button_reply", {}).get("title")
        elif interactive.get("type") == "list_reply":
            text_body = interactive.get("list_reply", {}).get("title")
            msg_type = "interactive_list_reply"
            list_msg_id = interactive.get("list_reply", {}).get("id")  # e.g. role_driver1
        else:
            text_body = "[interactive]"

    elif msg_type == "image":
        text_body = "[image]"
        media_id = msg.get("image", {}).get("id")

    elif msg_type == "audio":
        text_body = "[audio]"

    elif msg_type == "document":
        text_body = "[document]"

    elif msg_type == "location":
        loc = msg.get("location", {})
        latitude = loc.get("latitude")
        longitude = loc.get("longitude")
        text_body = "[location]"

    else:
        text_body = f"[{msg_type or 'unknown'}]"

    return msg_type or "unknown", list_msg_id, button_msg_id, text_body, media_id, latitude, longitude