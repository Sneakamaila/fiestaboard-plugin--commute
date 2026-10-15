"""Constants for the FiestaBoard Commute plugin."""

# Vestaboard Tile Dimensions
FLAGSHIP_WIDTH = 22
FLAGSHIP_HEIGHT = 6
NOTE_WIDTH = 15
NOTE_HEIGHT = 3

# Vestaboard Character Codes / Color Tiles
COLOR_RED = "{63}"
COLOR_ORANGE = "{64}"
COLOR_YELLOW = "{65}"
COLOR_GREEN = "{66}"
COLOR_BLUE = "{67}"
COLOR_VIOLET = "{68}"
COLOR_WHITE = "{69}"
COLOR_BLACK = "{70}"

# Traffic Condition Statuses
STATUS_CLEAR = "CLEAR"
STATUS_MODERATE = "MODERATE"
STATUS_HEAVY = "HEAVY"

# Default Thresholds (in minutes)
DEFAULT_DELAY_THRESHOLD_MINS = 5
DEFAULT_HEAVY_DELAY_THRESHOLD_MINS = 15

# Google Routes API v2
GOOGLE_ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GMP_SOLUTION_ID = "gmp_git_agentskills_v1"
ROUTES_FIELD_MASK = (
    "routes.duration,"
    "routes.staticDuration,"
    "routes.distanceMeters,"
    "routes.description,"
    "routes.warnings"
)

# TomTom Routing & Search API (100% Free Tier - 2,500 daily requests, no credit card)
TOMTOM_ROUTING_API_BASE = "https://api.tomtom.com/routing/1/calculateRoute"
TOMTOM_GEOCODE_API_BASE = "https://api.tomtom.com/search/2/geocode"

# HERE Technologies Routing v8 & Geocoding v7 API (30,000 monthly transactions)
HERE_ROUTING_API_BASE = "https://router.hereapi.com/v8/routes"
HERE_GEOCODE_API_BASE = "https://geocode.search.hereapi.com/v1/geocode"
