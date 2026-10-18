from __future__ import annotations

DARK = {
    "bg": "#0f1419",
    "text": "#d6dde6",
    "card": "#161b22",
    "border": "#2a313b",
    "muted": "#8b96a3",
    "accent": "#3ddc97",
    "input": "#1c222b",
    "hover": "#2c3440",
}

LIGHT = {
    "bg": "#f2f2f2",
    "text": "#1a1a1a",
    "card": "#ffffff",
    "border": "#c8ccd2",
    "muted": "#666666",
    "accent": "#0078d4",
    "input": "#ffffff",
    "hover": "#e0e0e0",
}

def colors(theme: str) -> dict:
    return LIGHT if theme == "light" else DARK
