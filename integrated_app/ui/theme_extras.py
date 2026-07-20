"""
theme_extras.py

AXIOM UI se liye gaye card/badge widgets ke liye color constants - jaan-boojh
kar tumhare EXISTING styles.qss ke colors use kiye hain (naya theme nahi hai,
same palette hai, bas Python constants ke roop mein taaki widgets_*.py files
inhe import kar sakein). Koi purani file iske bina break nahi hogi - ye
sirf naye widgets ke liye hai.
"""

BG_DEEP     = "#0A0E14"
BG_PANEL    = "#111823"
BG_PANEL_2  = "#182131"
BORDER      = "#232F40"

CYAN        = "#4FD1FF"   # tumhara existing accent color (styles.qss se)
CYAN_DIM    = "#2E8CB0"
VIOLET      = "#9B6BFF"   # chemistry accent (tumhare tutorial_3d.html ke --violet se)
PINK        = "#f5486b"   # biology accent
AMBER       = "#f59e0b"   # "SAMPLE"/warning badges
GREEN       = "#34d399"   # live/ok status

TEXT_PRIMARY   = "#E7ECF2"
TEXT_SECONDARY = "#8B97A6"
TEXT_MUTED     = "#4F5C6E"

FONT_DISPLAY = "Space Grotesk, Segoe UI, Arial"
FONT_MONO    = "JetBrains Mono, Consolas, monospace"

# Subject ke hisaab se color - HomePage/subject-selector cards mein use hoga
SUBJECT_COLORS = {
    "PHYSICS":   CYAN,
    "CHEMISTRY": VIOLET,
    "BIOLOGY":   PINK,
}
