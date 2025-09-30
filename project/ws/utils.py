def parse_cookies(cookie_header: str) -> dict:
    """Safely parse cookie header"""
    cookies = {}
    if not cookie_header:
        return cookies

    try:
        for item in cookie_header.split("; "):
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key] = value
    except Exception:
        pass  # Return empty dict on any parse error

    return cookies
