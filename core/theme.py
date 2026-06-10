BG       = "#0C1121"
CARD     = "#111827"
CARD2    = "#1A2235"
ACCENT   = "#3D7BF5"
BORDER   = "#1E2D45"
TEXT     = "#FFFFFF"
TEXT2    = "#6B7FA3"
TEXT3    = "#94A3B8"
SUCCESS  = "#22C55E"
ERROR    = "#EF4444"
WARN     = "#F97316"
TEAL     = "#14B8A6"

DAILY_GOAL = 20

SUBJECT_COLORS = [
    "#3B5998", "#1DA462", "#C0392B", "#8E44AD",
    "#E67E22", "#2980B9", "#16A085", "#D35400",
]

def subject_color(subject: str) -> str:
    return SUBJECT_COLORS[hash(subject) % len(SUBJECT_COLORS)]
