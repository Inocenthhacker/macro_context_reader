"""Economic Sentiment schemas — Cleveland Fed indices (PRD-102)."""

DISTRICT_NAMES = [
    "Boston", "New York", "Philadelphia", "Cleveland", "Richmond",
    "Atlanta", "Chicago", "St. Louis", "Minneapolis",
    "Kansas City", "Dallas", "San Francisco",
]

CSV_COLUMN_TO_DISTRICT = {
    "Atlanta": "Atlanta",
    "Boston": "Boston",
    "Chicago": "Chicago",
    "Cleveland": "Cleveland",
    "Dallas": "Dallas",
    "KC": "Kansas City",
    "Minneapolis": "Minneapolis",
    "NY": "New York",
    "Philadelphia": "Philadelphia",
    "Richmond": "Richmond",
    "SF": "San Francisco",
    "SL": "St. Louis",
}

DISTRICT_TO_CSV_COLUMN = {v: k for k, v in CSV_COLUMN_TO_DISTRICT.items()}
