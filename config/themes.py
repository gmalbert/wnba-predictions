"""Curated Streamlit themes for the WNBA Predictions app.

All palettes are derived from the brand identity in the logo:
- Deep navy/violet  #100030 (HER HOOPS silhouette + text)
- Vivid magenta     #F03060 (EDGE accent)

15 daytime (light) themes + 15 nighttime (dark) themes. Each theme is a dict
matching Streamlit's [theme] config keys: primaryColor, backgroundColor,
secondaryBackgroundColor, textColor, font.

Keyed by a short slug. Theme switching re-runs the app via st.rerun().
"""

# ── Shared brand anchors ──────────────────────────────────────────────────────
NAVY = "#100030"
MAGENTA = "#F03060"
NAVY_DARK = "#0A0018"  # deeper navy for dark surfaces
NAVY_ALT = "#1B0040"   # lighter navy for dark surface contrast

# Light surfaces tinted toward the brand hue (whisper of violet/magenta)
LIGHT_BG = "#FCFAF9"      # warm off-white
LIGHT_BG_ALT = "#F3F0F6"  # pale violet-gray
LIGHT_BG_2 = "#FAF6FB"    # pale magenta tint
LIGHT_BG_3 = "#EEF0F8"    # pale blue-violet tint
LIGHT_BG_4 = "#FDF6F4"    # pale coral tint
LIGHT_BG_5 = "#F4F7F5"    # pale sage tint
LIGHT_BG_6 = "#F6F4EF"    # warm cream
LIGHT_TEXT = "#1B1026"    # near-black violet text

# Dark surfaces tinted toward the brand hue
DARK_BG = "#0E0820"       # deep violet-black
DARK_BG_ALT = "#171031"   # raised surface
DARK_BG_2 = "#1C1440"     # violet-indigo
DARK_BG_3 = "#120A2E"     # slightly lighter violet-black
DARK_BG_4 = "#201735"     # muted plum
DARK_BG_5 = "#0D1B2A"     # navy-night
DARK_TEXT = "#F2EEFA"     # soft violet-white text

# ── Daytime (light) themes ────────────────────────────────────────────────────
DAYTIME = {
    "brand": {
        "name": "Brand Light",
        "description": "Navy + magenta on warm off-white. Closest to the logo.",
        "primaryColor": MAGENTA,
        "backgroundColor": LIGHT_BG,
        "secondaryBackgroundColor": LIGHT_BG_ALT,
        "textColor": LIGHT_TEXT,
        "font": "sans serif",
    },
    "magenta_blush": {
        "name": "Magenta Blush",
        "description": "Magenta accents on a pale rose surface.",
        "primaryColor": MAGENTA,
        "backgroundColor": LIGHT_BG_2,
        "secondaryBackgroundColor": "#F6ECF4",
        "textColor": LIGHT_TEXT,
        "font": "sans serif",
    },
    "violet_glacier": {
        "name": "Violet Glacier",
        "description": "Cool violet surfaces with magenta primary.",
        "primaryColor": MAGENTA,
        "backgroundColor": LIGHT_BG_3,
        "secondaryBackgroundColor": "#E4E8F6",
        "textColor": "#16122E",
        "font": "sans serif",
    },
    "coral_reef": {
        "name": "Coral Reef",
        "description": "Warm coral-tinted light theme, magenta action color.",
        "primaryColor": MAGENTA,
        "backgroundColor": LIGHT_BG_4,
        "secondaryBackgroundColor": "#F7E8E4",
        "textColor": "#26141A",
        "font": "sans serif",
    },
    "sage_mist": {
        "name": "Sage Mist",
        "description": "Calm sage-gray light surfaces with magenta accent.",
        "primaryColor": MAGENTA,
        "backgroundColor": LIGHT_BG_5,
        "secondaryBackgroundColor": "#E7EFE9",
        "textColor": "#14201B",
        "font": "sans serif",
    },
    "cream_linen": {
        "name": "Cream Linen",
        "description": "Soft cream light theme, navy text, magenta accent.",
        "primaryColor": MAGENTA,
        "backgroundColor": LIGHT_BG_6,
        "secondaryBackgroundColor": "#EFEAE0",
        "textColor": "#1F1826",
        "font": "serif",
    },
    "graphite_ice": {
        "name": "Graphite Ice",
        "description": "Neutral gray light theme, restrained magenta.",
        "primaryColor": "#D6286A",
        "backgroundColor": "#FAFAFC",
        "secondaryBackgroundColor": "#F0F0F4",
        "textColor": "#1A1A24",
        "font": "sans serif",
    },
    "peach_fizz": {
        "name": "Peach Fizz",
        "description": "Peachy light theme with raspberry primary.",
        "primaryColor": "#E6396E",
        "backgroundColor": "#FDF7F4",
        "secondaryBackgroundColor": "#F8EDE7",
        "textColor": "#24141A",
        "font": "sans serif",
    },
    "lilac_dawn": {
        "name": "Lilac Dawn",
        "description": "Lilac-tinted light theme, deep violet text.",
        "primaryColor": "#C2337E",
        "backgroundColor": "#FBFAFE",
        "secondaryBackgroundColor": "#F1EAF9",
        "textColor": "#1E1430",
        "font": "sans serif",
    },
    "silver_rose": {
        "name": "Silver Rose",
        "description": "Silver-gray light theme with magenta pop.",
        "primaryColor": MAGENTA,
        "backgroundColor": "#F7F7F9",
        "secondaryBackgroundColor": "#ECECF1",
        "textColor": "#1C1C26",
        "font": "sans serif",
    },
    "cloud_white": {
        "name": "Cloud White",
        "description": "Clean bright white light theme, magenta primary.",
        "primaryColor": MAGENTA,
        "backgroundColor": "#FFFFFF",
        "secondaryBackgroundColor": "#F3F0F6",
        "textColor": "#171120",
        "font": "sans serif",
    },
    "buttercream": {
        "name": "Buttercream",
        "description": "Warm buttery light theme, magenta + navy contrast.",
        "primaryColor": "#D62A68",
        "backgroundColor": "#FFFDF8",
        "secondaryBackgroundColor": "#F7F0E2",
        "textColor": "#201A24",
        "font": "sans serif",
    },
    "mint_frost": {
        "name": "Mint Frost",
        "description": "Cool mint light theme, raspberry accent.",
        "primaryColor": "#E02B6D",
        "backgroundColor": "#FBFDFC",
        "secondaryBackgroundColor": "#EAF3EF",
        "textColor": "#13201B",
        "font": "sans serif",
    },
    "rose_quartz": {
        "name": "Rose Quartz",
        "description": "Rosy quartz light theme, deep magenta primary.",
        "primaryColor": "#C2185B",
        "backgroundColor": "#FDF9FA",
        "secondaryBackgroundColor": "#F6E8EE",
        "textColor": "#231018",
        "font": "serif",
    },
    "porcelain": {
        "name": "Porcelain",
        "description": "Cool porcelain-white light theme, magenta primary.",
        "primaryColor": MAGENTA,
        "backgroundColor": "#FBFBFC",
        "secondaryBackgroundColor": "#EEF0F4",
        "textColor": "#16181F",
        "font": "sans serif",
    },
}

# ── Nighttime (dark) themes ───────────────────────────────────────────────────
NIGHTTIME = {
    "brand_dark": {
        "name": "Brand Dark",
        "description": "Deep navy-violet dark theme, magenta primary.",
        "primaryColor": MAGENTA,
        "backgroundColor": DARK_BG,
        "secondaryBackgroundColor": DARK_BG_ALT,
        "textColor": DARK_TEXT,
        "font": "sans serif",
    },
    "midnight_berry": {
        "name": "Midnight Berry",
        "description": "Dark violet night, magenta berry accents.",
        "primaryColor": "#FF4D8D",
        "backgroundColor": DARK_BG,
        "secondaryBackgroundColor": DARK_BG_2,
        "textColor": DARK_TEXT,
        "font": "sans serif",
    },
    "indigo_night": {
        "name": "Indigo Night",
        "description": "Indigo-black dark theme, vivid magenta primary.",
        "primaryColor": MAGENTA,
        "backgroundColor": DARK_BG_3,
        "secondaryBackgroundColor": "#1A1240",
        "textColor": DARK_TEXT,
        "font": "sans serif",
    },
    "plum_dusk": {
        "name": "Plum Dusk",
        "description": "Muted plum dark surfaces, raspberry accent.",
        "primaryColor": "#F03A7E",
        "backgroundColor": DARK_BG_4,
        "secondaryBackgroundColor": "#2A1E44",
        "textColor": "#F4EDFA",
        "font": "sans serif",
    },
    "navy_night": {
        "name": "Navy Night",
        "description": "Navy-blue night theme, magenta primary.",
        "primaryColor": "#FF3D7F",
        "backgroundColor": DARK_BG_5,
        "secondaryBackgroundColor": "#16283A",
        "textColor": "#EAF2FB",
        "font": "sans serif",
    },
    "obsidian_rose": {
        "name": "Obsidian Rose",
        "description": "Near-black obsidian, magenta rose accents.",
        "primaryColor": "#F54B8B",
        "backgroundColor": "#0A0713",
        "secondaryBackgroundColor": "#171226",
        "textColor": "#F1ECF8",
        "font": "sans serif",
    },
    "aubergine": {
        "name": "Aubergine",
        "description": "Eggplant-violet dark theme, hot magenta.",
        "primaryColor": "#FF3E8A",
        "backgroundColor": "#140B22",
        "secondaryBackgroundColor": "#1F1333",
        "textColor": "#F4EDFB",
        "font": "sans serif",
    },
    "crimson_eclipse": {
        "name": "Crimson Eclipse",
        "description": "Dark crimson-night, magenta energy.",
        "primaryColor": "#E6336E",
        "backgroundColor": "#140A14",
        "secondaryBackgroundColor": "#201322",
        "textColor": "#FAEFF4",
        "font": "sans serif",
    },
    "wine_violet": {
        "name": "Wine Violet",
        "description": "Deep wine + violet dark, magenta accent.",
        "primaryColor": "#D6286A",
        "backgroundColor": "#120B1C",
        "secondaryBackgroundColor": "#1D1429",
        "textColor": "#F2EBF7",
        "font": "sans serif",
    },
    "graphite_onyx": {
        "name": "Graphite Onyx",
        "description": "Neutral graphite dark, restrained magenta.",
        "primaryColor": "#E6336E",
        "backgroundColor": "#121218",
        "secondaryBackgroundColor": "#1C1C24",
        "textColor": "#EDEDF3",
        "font": "sans serif",
    },
    "charcoal_berry": {
        "name": "Charcoal Berry",
        "description": "Charcoal dark, berry magenta primary.",
        "primaryColor": "#F0458C",
        "backgroundColor": "#101016",
        "secondaryBackgroundColor": "#1A1A22",
        "textColor": "#F1EEF6",
        "font": "sans serif",
    },
    "storm_plum": {
        "name": "Storm Plum",
        "description": "Stormy gray-plum dark, magenta pop.",
        "primaryColor": "#E9377D",
        "backgroundColor": "#14121E",
        "secondaryBackgroundColor": "#1E1B2C",
        "textColor": "#F0EBF8",
        "font": "sans serif",
    },
    "deep_mulberry": {
        "name": "Deep Mulberry",
        "description": "Rich mulberry-violet dark theme.",
        "primaryColor": "#F14B93",
        "backgroundColor": "#160D24",
        "secondaryBackgroundColor": "#221636",
        "textColor": "#F5EEFB",
        "font": "sans serif",
    },
    "midnight_slate": {
        "name": "Midnight Slate",
        "description": "Cool slate dark, raspberry accent.",
        "primaryColor": "#E62E70",
        "backgroundColor": "#0E1118",
        "secondaryBackgroundColor": "#181D28",
        "textColor": "#EAEEF6",
        "font": "sans serif",
    },
    "vantablack_rose": {
        "name": "Vantablack Rose",
        "description": "Extreme near-black, hot magenta rose.",
        "primaryColor": "#FF4D99",
        "backgroundColor": "#07060C",
        "secondaryBackgroundColor": "#12101C",
        "textColor": "#F5EFFA",
        "font": "sans serif",
    },
}

ALL_THEMES = {**DAYTIME, **NIGHTTIME}


def get_theme(slug: str) -> dict:
    """Return a theme dict by slug; falls back to Brand Dark."""
    return ALL_THEMES.get(slug, NIGHTTIME["brand_dark"])


def theme_options(period: str) -> list[str]:
    """Return slugs for a period ('daytime' | 'nighttime'), grouped by name."""
    source = DAYTIME if period == "daytime" else NIGHTTIME
    return [f"{slug} · {meta['name']}" for slug, meta in source.items()]


def slug_from_option(option: str) -> str:
    return option.split(" · ")[0]
