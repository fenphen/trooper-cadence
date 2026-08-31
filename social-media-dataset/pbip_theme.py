#!/usr/bin/env python3
"""CampusPulse report theme (validated against Microsoft's report theme schema)."""

THEME_FILE = "CampusPulse.json"


def build_theme():
    return {
        "name": "CampusPulse",
        # Ordered so the first few series colours stay distinguishable in both
        # light and dark viewing, and so nothing reads as "good/bad" by accident.
        "dataColors": [
            "#2E6BE6", "#8B2FD6", "#0E8C6A", "#D6600F", "#B5197A", "#127C9E",
            "#B3261E", "#6E7A8A", "#4C9AFF", "#B478E8", "#3FB68F", "#F0913F",
            "#E05FA8", "#3FAFD0", "#D9615A", "#98A2B3", "#1A3F8F", "#5B1B8F",
            "#08543F", "#8A3C06",
        ],
        "background": "#FFFFFF",
        "secondaryBackground": "#F3F4F7",
        "foreground": "#252423",
        "tableAccent": "#2E6BE6",
        "good": "#0E8C6A",
        "neutral": "#B58900",
        "bad": "#B3261E",
        "maximum": "#2E6BE6",
        "center": "#C9D3E4",
        "minimum": "#F3F4F7",
        "hyperlink": "#2E6BE6",
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 13,
                      "color": "#252423"},
            "label": {"fontFace": "Segoe UI", "fontSize": 10,
                      "color": "#3B3A39"},
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 26,
                        "color": "#2E6BE6"},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11,
                       "color": "#252423"},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}},
                                    "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": "#E1E4EA"}},
                                "radius": 6}],
                    "title": [{"show": True, "fontColor": {"solid": {"color": "#252423"}},
                               "fontSize": 11, "bold": True, "alignment": "left"}],
                    "visualHeader": [{"show": False}],
                }
            },
            "card": {
                "*": {
                    "labels": [{"fontSize": 24, "bold": True,
                                "color": {"solid": {"color": "#2E6BE6"}}}],
                    "categoryLabels": [{"show": False}],
                }
            },
            "slicer": {
                "*": {
                    "header": [{"show": True, "fontSize": 9, "bold": True,
                                "fontColor": {"solid": {"color": "#605E5C"}}}],
                    "items": [{"fontSize": 9}],
                }
            },
            "textbox": {
                "*": {
                    "background": [{"show": False}],
                    "border": [{"show": False}],
                }
            },
        },
    }
