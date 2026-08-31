#!/usr/bin/env python3
"""
CampusPulse Media - synthetic social-media audience dataset generator.

Generates 100% FAKE (but realistic-looking) data simulating what a social media
marketing company could assemble about college students from ad-platform
exports, for a Power BI teaching dashboard about the data social media
companies collect.

- Every person, handle, email, phone number, device ID and metric is synthetic.
- Advertiser brands are fictional. Universities are real institutions used
  only as fictional settings; no rows describe real people.
- Deterministic: run with the same SEED and you get identical files.

Usage:  python3 generate_data.py     (writes CSVs into ./data/)
Stdlib only - no dependencies.
"""

import csv
import hashlib
import math
import os
import random
from datetime import date, timedelta

# ---------------------------------------------------------------- config ----
SEED = 42
N_USERS = 2000
START_DATE = date(2026, 6, 1)
END_DATE = date(2026, 8, 31)
SEMESTER_START = date(2026, 8, 24)  # behavior shifts when fall term begins

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "data")

rng = random.Random(SEED)


# --------------------------------------------------------------- helpers ----
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def frac_int(expected, cap=None):
    """Integer draw whose long-run mean equals `expected`."""
    if expected <= 0:
        return 0
    i = int(expected)
    i += 1 if rng.random() < (expected - i) else 0
    if cap is not None:
        i = min(i, cap)
    return i


def wchoice(pairs):
    """pairs = [(value, weight), ...]"""
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs])[0]


def allocate(total, weights):
    """Split integer `total` across buckets proportional to weights (largest
    remainder), so daily rows reconcile exactly with campaign totals."""
    n = len(weights)
    if n == 0 or total <= 0:
        return [0] * n
    s = sum(weights)
    if s <= 0:
        weights = [1.0] * n
        s = float(n)
    raw = [total * w / s for w in weights]
    base = [int(v) for v in raw]
    order = sorted(range(n), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[: total - sum(base)]:
        base[i] += 1
    return base


def fake_uuid():
    h = "".join(rng.choice("0123456789abcdef") for _ in range(32))
    return "-".join([h[0:8], h[8:12], h[12:16], h[16:20], h[20:32]])


def write_csv(name, header, rows):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def b(x):
    return "TRUE" if x else "FALSE"


# ------------------------------------------------------------ static data ---
UNIVERSITIES = [
    # name, city, state, lat, lon, weight
    ("Ohio State University", "Columbus", "OH", 40.0067, -83.0305, 9),
    ("University of Michigan", "Ann Arbor", "MI", 42.2780, -83.7382, 7),
    ("University of Texas at Austin", "Austin", "TX", 30.2849, -97.7341, 9),
    ("Texas A&M University", "College Station", "TX", 30.6188, -96.3365, 8),
    ("University of Florida", "Gainesville", "FL", 29.6436, -82.3549, 8),
    ("Florida State University", "Tallahassee", "FL", 30.4419, -84.2985, 6),
    ("University of Georgia", "Athens", "GA", 33.9480, -83.3773, 7),
    ("Penn State University", "State College", "PA", 40.7982, -77.8599, 7),
    ("Arizona State University", "Tempe", "AZ", 33.4242, -111.9281, 9),
    ("University of Washington", "Seattle", "WA", 47.6553, -122.3035, 6),
    ("UCLA", "Los Angeles", "CA", 34.0689, -118.4452, 6),
    ("University of Wisconsin-Madison", "Madison", "WI", 43.0766, -89.4125, 6),
    ("University of Minnesota", "Minneapolis", "MN", 44.9740, -93.2277, 5),
    ("University of Alabama", "Tuscaloosa", "AL", 33.2140, -87.5391, 5),
    ("New York University", "New York", "NY", 40.7295, -73.9965, 4),
]

HOMETOWNS_BY_STATE = {
    "OH": [("Cleveland", 41.4993, -81.6944), ("Cincinnati", 39.1031, -84.5120),
           ("Dayton", 39.7589, -84.1916), ("Toledo", 41.6528, -83.5379)],
    "MI": [("Detroit", 42.3314, -83.0458), ("Grand Rapids", 42.9634, -85.6681),
           ("Lansing", 42.7325, -84.5555), ("Troy", 42.6064, -83.1498)],
    "TX": [("Houston", 29.7604, -95.3698), ("Dallas", 32.7767, -96.7970),
           ("San Antonio", 29.4241, -98.4936), ("Fort Worth", 32.7555, -97.3308),
           ("El Paso", 31.7619, -106.4850), ("Plano", 33.0198, -96.6989)],
    "FL": [("Miami", 25.7617, -80.1918), ("Orlando", 28.5384, -81.3789),
           ("Tampa", 27.9506, -82.4572), ("Jacksonville", 30.3322, -81.6557)],
    "GA": [("Atlanta", 33.7490, -84.3880), ("Savannah", 32.0809, -81.0912),
           ("Marietta", 33.9526, -84.5499), ("Augusta", 33.4735, -82.0105)],
    "PA": [("Philadelphia", 39.9526, -75.1652), ("Pittsburgh", 40.4406, -79.9959),
           ("Allentown", 40.6084, -75.4902), ("Erie", 42.1292, -80.0851)],
    "AZ": [("Phoenix", 33.4484, -112.0740), ("Tucson", 32.2226, -110.9747),
           ("Mesa", 33.4152, -111.8315), ("Scottsdale", 33.4942, -111.9261)],
    "WA": [("Spokane", 47.6588, -117.4260), ("Tacoma", 47.2529, -122.4443),
           ("Bellevue", 47.6101, -122.2015), ("Vancouver", 45.6387, -122.6615)],
    "CA": [("San Diego", 32.7157, -117.1611), ("Sacramento", 38.5816, -121.4944),
           ("San Jose", 37.3382, -121.8863), ("Fresno", 36.7378, -119.7871),
           ("Irvine", 33.6846, -117.8265)],
    "WI": [("Milwaukee", 43.0389, -87.9065), ("Green Bay", 44.5133, -88.0133),
           ("Kenosha", 42.5847, -87.8212), ("Appleton", 44.2619, -88.4154)],
    "MN": [("St. Paul", 44.9537, -93.0900), ("Rochester", 44.0121, -92.4802),
           ("Duluth", 46.7867, -92.1005), ("Bloomington", 44.8408, -93.2983)],
    "AL": [("Birmingham", 33.5186, -86.8104), ("Huntsville", 34.7304, -86.5861),
           ("Montgomery", 32.3668, -86.3000), ("Mobile", 30.6954, -88.0399)],
    "NY": [("Brooklyn", 40.6782, -73.9442), ("Buffalo", 42.8864, -78.8784),
           ("Rochester", 43.1566, -77.6088), ("Syracuse", 43.0481, -76.1474)],
}
HOMETOWNS_OTHER = [
    ("Chicago", "IL", 41.8781, -87.6298), ("Denver", "CO", 39.7392, -104.9903),
    ("Nashville", "TN", 36.1627, -86.7816), ("Charlotte", "NC", 35.2271, -80.8431),
    ("St. Louis", "MO", 38.6270, -90.1994), ("Kansas City", "MO", 39.0997, -94.5786),
    ("Indianapolis", "IN", 39.7684, -86.1581), ("Louisville", "KY", 38.2527, -85.7585),
    ("New Orleans", "LA", 29.9511, -90.0715), ("Las Vegas", "NV", 36.1699, -115.1398),
    ("Portland", "OR", 45.5152, -122.6784), ("Boise", "ID", 43.6150, -116.2023),
    ("Salt Lake City", "UT", 40.7608, -111.8910), ("Oklahoma City", "OK", 35.4676, -97.5164),
    ("Omaha", "NE", 41.2565, -95.9345), ("Newark", "NJ", 40.7357, -74.1724),
    ("Boston", "MA", 42.3601, -71.0589), ("Hartford", "CT", 41.7658, -72.6734),
    ("Richmond", "VA", 37.5407, -77.4360), ("Columbia", "SC", 34.0007, -81.0348),
]

FIRST_F = ["Emma", "Olivia", "Ava", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia",
           "Harper", "Evelyn", "Abigail", "Emily", "Ella", "Elizabeth", "Camila", "Luna",
           "Sofia", "Avery", "Mila", "Aria", "Scarlett", "Penelope", "Layla", "Chloe",
           "Victoria", "Madison", "Eleanor", "Grace", "Nora", "Riley", "Zoey", "Hannah",
           "Hazel", "Lily", "Ellie", "Violet", "Lillian", "Zoe", "Stella", "Aurora",
           "Natalie", "Emilia", "Everly", "Leah", "Aubrey", "Willow", "Addison", "Lucy",
           "Audrey", "Bella", "Brooklyn", "Paisley", "Savannah", "Skylar", "Naomi",
           "Maya", "Kennedy", "Kinsley", "Allison", "Gabriella", "Sarah", "Madelyn",
           "Destiny", "Jasmine", "Priya", "Ananya", "Mei", "Yuna", "Fatima", "Aisha",
           "Valentina", "Camille", "Simone", "Nia", "Imani", "Alondra", "Ximena", "Daniela"]
FIRST_M = ["Liam", "Noah", "Oliver", "Elijah", "William", "James", "Benjamin", "Lucas",
           "Henry", "Alexander", "Mason", "Michael", "Ethan", "Daniel", "Jacob", "Logan",
           "Jackson", "Levi", "Sebastian", "Mateo", "Jack", "Owen", "Theodore", "Aiden",
           "Samuel", "Joseph", "John", "David", "Wyatt", "Matthew", "Luke", "Asher",
           "Carter", "Julian", "Grayson", "Leo", "Jayden", "Gabriel", "Isaac", "Lincoln",
           "Anthony", "Hudson", "Dylan", "Ezra", "Thomas", "Charles", "Christopher",
           "Jaxon", "Maverick", "Josiah", "Isaiah", "Andrew", "Elias", "Joshua", "Nathan",
           "Caleb", "Ryan", "Adrian", "Miles", "Eli", "Nolan", "Christian", "Aaron",
           "Cameron", "Ezekiel", "Colton", "Luca", "Landon", "Hunter", "Jonathan",
           "Santiago", "Axel", "Easton", "Cooper", "Jeremiah", "Angel", "Roman", "Connor",
           "Jameson", "Robert", "Marcus", "Malik", "Darius", "Andre", "Jamal", "Diego",
           "Carlos", "Raj", "Arjun", "Wei", "Jin", "Omar", "Tariq", "Mohammed", "Kai"]
FIRST_N = ["Alex", "Jordan", "Taylor", "Casey", "Rowan", "Sage", "River", "Phoenix",
           "Skyler", "Emerson", "Finley", "Dakota", "Quinn"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
        "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
        "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
        "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
        "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
        "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
        "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
        "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
        "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson", "Watson",
        "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz",
        "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long",
        "Ross", "Foster", "Jimenez", "Singh", "Chen", "Wang", "Li", "Park", "Choi",
        "Tran", "Le", "Pham", "Kaur", "Sharma", "Ali", "Khan", "Hassan", "Okafor",
        "Osei", "Mensah", "Silva", "Santos", "Oliveira", "Fernandez", "Vargas", "Rossi",
        "Yamamoto", "Tanaka", "Sato", "Haddad", "Murray", "Sullivan", "Walsh", "Byrne",
        "Fraser", "Schmidt", "Muller", "Weber", "Wagner", "Becker", "Hoffman", "Larsen",
        "Hansen", "Andersen", "Lindberg", "Virtanen", "Dubois", "Laurent", "Moreau",
        "Janssen", "Visser", "Papadopoulos", "Novak", "Kowalski", "Ivanov"]

MAJORS = [("Business Administration", 9), ("Psychology", 7), ("Nursing", 6),
          ("Biology", 6), ("Computer Science", 6), ("Marketing", 5),
          ("Communications", 5), ("Mechanical Engineering", 4), ("Finance", 4),
          ("Information Systems", 4), ("Data Analytics", 4), ("Kinesiology", 4),
          ("Education", 4), ("Political Science", 3), ("Economics", 3),
          ("Graphic Design", 3), ("Criminal Justice", 3), ("Public Health", 3),
          ("Accounting", 3), ("Undeclared", 3), ("English", 2), ("History", 2),
          ("Chemistry", 2), ("Mathematics", 2), ("Environmental Science", 2),
          ("Music", 2), ("Journalism", 2), ("Sociology", 2),
          ("Civil Engineering", 2), ("Electrical Engineering", 2)]

CLASS_YEARS = [("Freshman", 22, 18), ("Sophomore", 22, 19), ("Junior", 21, 20),
               ("Senior", 21, 21), ("Graduate", 14, 23)]

HOUSING = [("Dorm / Residence Hall", 34), ("Off-Campus Apartment", 38),
           ("Greek Housing", 8), ("University Apartment", 10), ("Lives at Home", 10)]

RELATIONSHIP = [("Single", 55), ("In a relationship", 32),
                ("It's complicated", 6), ("Prefer not to say", 7)]

PLATFORM_INFO = [
    ("Instagram", "Meta Platforms", "Menlo Park, CA", 2010,
     "Photos & short video (Reels)", "https://privacycenter.instagram.com/policy"),
    ("TikTok", "ByteDance", "Culver City, CA (US)", 2016,
     "Short-form video", "https://www.tiktok.com/legal/page/us/privacy-policy/en"),
    ("Snapchat", "Snap Inc.", "Santa Monica, CA", 2011,
     "Ephemeral photo & video", "https://values.snap.com/privacy/privacy-policy"),
    ("X (Twitter)", "X Corp.", "Bastrop, TX", 2006,
     "Short text & video posts", "https://x.com/en/privacy"),
    ("Facebook", "Meta Platforms", "Menlo Park, CA", 2004,
     "Mixed feed, groups & marketplace", "https://www.facebook.com/privacy/policy/"),
]

# behavioral tuning per platform
PCFG = {
    "Instagram":   dict(adopt=0.95, base_min=52, sess_len=7.5, cpm_content=3.2,
                        video_share=0.58, comp_mu=56, comp_sd=13, like=(0.050, 0.020),
                        ad_load=0.105, p_active=0.90, story=True, ctr=(0.009, 0.004),
                        wkend=1.04, fwd_mult=1.0, cpm_usd=11.4),
    "TikTok":      dict(adopt=0.86, base_min=76, sess_len=11.0, cpm_content=2.6,
                        video_share=0.97, comp_mu=68, comp_sd=12, like=(0.080, 0.030),
                        ad_load=0.070, p_active=0.92, story=False, ctr=(0.010, 0.004),
                        wkend=1.08, fwd_mult=1.6, cpm_usd=9.2),
    "Snapchat":    dict(adopt=0.78, base_min=42, sess_len=4.5, cpm_content=4.0,
                        video_share=0.62, comp_mu=61, comp_sd=13, like=(0.015, 0.008),
                        ad_load=0.065, p_active=0.88, story=True, ctr=(0.007, 0.003),
                        wkend=1.14, fwd_mult=1.3, cpm_usd=7.8),
    "X (Twitter)": dict(adopt=0.36, base_min=24, sess_len=5.0, cpm_content=7.5,
                        video_share=0.28, comp_mu=44, comp_sd=14, like=(0.030, 0.015),
                        ad_load=0.085, p_active=0.72, story=False, ctr=(0.008, 0.004),
                        wkend=0.92, fwd_mult=0.9, cpm_usd=6.3),
    "Facebook":    dict(adopt=0.26, base_min=14, sess_len=4.0, cpm_content=3.0,
                        video_share=0.38, comp_mu=41, comp_sd=14, like=(0.040, 0.020),
                        ad_load=0.115, p_active=0.55, story=True, ctr=(0.011, 0.005),
                        wkend=1.00, fwd_mult=0.8, cpm_usd=10.1),
}
PLATFORM_ORDER = ["Instagram", "TikTok", "Snapchat", "X (Twitter)", "Facebook"]

# interest taxonomy: (name, category, driver latent or None, driver weight)
INTEREST_DEFS = [
    ("Fitness & Gym Life", "Sports & Fitness", "athletic", 0.80),
    ("Running & Outdoor Cardio", "Sports & Fitness", "athletic", 0.60),
    ("College Football", "Sports & Fitness", "sports_fan", 0.80),
    ("College Basketball", "Sports & Fitness", "sports_fan", 0.70),
    ("Pro Sports", "Sports & Fitness", "sports_fan", 0.60),
    ("Intramural & Rec Sports", "Sports & Fitness", "athletic", 0.50),
    ("Foodie & Restaurants", "Food & Drink", "foodie", 0.80),
    ("Cooking & Easy Recipes", "Food & Drink", "foodie", 0.60),
    ("Coffee Culture", "Food & Drink", "foodie", 0.50),
    ("Late-Night Food Delivery", "Food & Drink", "night_owl", 0.55),
    ("Streaming TV & Movies", "Entertainment", "video_affinity", 0.60),
    ("Anime & Manga", "Entertainment", "gamer", 0.45),
    ("Reality TV", "Entertainment", None, 0.0),
    ("Stand-up & Comedy Clips", "Entertainment", "video_affinity", 0.50),
    ("Celebrity & Pop Culture", "Entertainment", "aesthetic", 0.40),
    ("Video Games", "Gaming & Tech", "gamer", 0.85),
    ("Esports", "Gaming & Tech", "gamer", 0.60),
    ("PC Building & Hardware", "Gaming & Tech", "techie", 0.60),
    ("New Tech & Gadgets", "Gaming & Tech", "techie", 0.75),
    ("AI Tools & Apps", "Gaming & Tech", "techie", 0.60),
    ("Coding & Software Dev", "Gaming & Tech", "techie", 0.55),
    ("Streetwear & Sneakers", "Fashion & Beauty", "aesthetic", 0.70),
    ("Thrifting & Vintage Fashion", "Fashion & Beauty", "aesthetic", 0.60),
    ("Beauty & Skincare", "Fashion & Beauty", "aesthetic", 0.65),
    ("Fast Fashion Hauls", "Fashion & Beauty", "shopper", 0.60),
    ("Live Music & Festivals", "Music", "music_fan", 0.80),
    ("Hip-Hop & R&B", "Music", "music_fan", 0.60),
    ("Pop & Charts", "Music", "music_fan", 0.55),
    ("Indie & Alt", "Music", "music_fan", 0.50),
    ("K-Pop", "Music", "music_fan", 0.45),
    ("Country", "Music", "music_fan", 0.40),
    ("EDM & House", "Music", "music_fan", 0.45),
    ("Travel & Adventure", "Travel", "wanderlust", 0.80),
    ("Study Abroad", "Travel", "wanderlust", 0.55),
    ("Road Trips & National Parks", "Travel", "wanderlust", 0.50),
    ("Personal Finance & Investing", "Money & Career", "finance_minded", 0.80),
    ("Side Hustles & Entrepreneurship", "Money & Career", "finance_minded", 0.60),
    ("Internships & Career Prep", "Money & Career", "studious", 0.60),
    ("Crypto & Trading", "Money & Career", "finance_minded", 0.45),
    ("Mental Health & Mindfulness", "Lifestyle & Wellness", "wellness", 0.75),
    ("Yoga & Pilates", "Lifestyle & Wellness", "wellness", 0.55),
    ("Healthy Eating & Meal Prep", "Lifestyle & Wellness", "wellness", 0.60),
    ("Greek Life", "Lifestyle & Wellness", "sociability", 0.50),
    ("Campus Events & Nightlife", "Lifestyle & Wellness", "sociability", 0.70),
    ("Pets & Animals", "Lifestyle & Wellness", None, 0.0),
    ("Photography & Content Creation", "Lifestyle & Wellness", "creator", 0.70),
    ("Study Hacks & Productivity", "Lifestyle & Wellness", "studious", 0.70),
    ("Climate & Sustainability", "Causes & News", "activist", 0.70),
    ("Politics & Current Events", "Causes & News", "activist", 0.75),
    ("Volunteering & Social Impact", "Causes & News", "activist", 0.55),
]

SEGMENT_DEFS = [
    # id-suffix handled later: (name, tagline, driver, threshold, base_cpm, rule_text)
    ("Late-Night Scrollers", "They're awake at 1 a.m. - your brand should be too.",
     "night_owl", 0.70, 7.50, "Night-owl chronotype; >45% of usage after 10 p.m."),
    ("Campus Gym Rats", "Fitness-first students who buy gear, supplements and memberships.",
     "athletic", 0.68, 9.00, "High fitness engagement and gym-related interest affinity."),
    ("Budget Foodies", "Big cravings, student budgets - delivery deals win them over.",
     "foodie", 0.66, 8.00, "Strong food content engagement with low discretionary spend."),
    ("Gamers & Streamers", "Console, PC and mobile players with strong brand loyalty.",
     "gamer", 0.66, 10.50, "High gaming interest affinity and gaming content dwell time."),
    ("Trend-Setting Fashionistas", "First to every micro-trend; haul and outfit content daily.",
     "aesthetic", 0.70, 11.00, "High fashion/beauty affinity and shopping content engagement."),
    ("Wanderlust Planners", "Already saving for the next trip - reach them before they book.",
     "wanderlust", 0.72, 9.50, "High travel-content affinity and trip-planning signals."),
    ("Money-Minded Strivers", "Future founders and finance nerds building credit early.",
     "finance_minded", 0.66, 12.00, "Finance/business interest affinity or business-school major."),
    ("Game-Day Superfans", "Live and die with the team; peak activity on game days.",
     "sports_fan", 0.70, 8.50, "High college-sports affinity and game-day usage spikes."),
    ("Festival & Live Music Crowd", "Ticket buyers and merch collectors who travel for shows.",
     "music_fan", 0.74, 9.00, "High live-music affinity and event-content engagement."),
    ("Mindful & Wellness-Focused", "Self-care spenders: apps, journals, matcha and mats.",
     "wellness", 0.70, 8.50, "High wellness-content affinity and mindfulness app signals."),
    ("Impulse Deal Hunters", "See it, want it, buy it - highest CTR audience we sell.",
     "shopper", 0.70, 10.00, "High impulse-buying score and shopping-ad click history."),
    ("Micro-Influencers & Creators", "8k+ followings; buy them once, they sell for you all semester.",
     "creator", 0.72, 18.00, "Creator behavior or 8,000+ followers on any platform."),
]

CAMPAIGN_DEFS = [
    # advertiser, campaign name, vertical, objective, segment index, platforms, start, end, AOV
    ("Voltberry Energy", "Summer Session All-Nighters", "Food & Beverage", "Awareness",
     0, ["TikTok", "Instagram"], date(2026, 6, 8), date(2026, 7, 5), 12),
    ("IronLeaf Fitness", "Summer Shred Student Pass", "Health & Fitness", "Conversions",
     1, ["Instagram", "TikTok"], date(2026, 6, 1), date(2026, 7, 15), 89),
    ("SnackOwl Delivery", "Midnight Munchies, Delivered", "Food Delivery", "App Installs",
     2, ["Snapchat", "TikTok"], date(2026, 6, 15), date(2026, 8, 15), 24),
    ("PixelForge Gear", "Level Up Summer Drop", "Gaming & Tech", "Conversions",
     3, ["X (Twitter)", "TikTok"], date(2026, 7, 1), date(2026, 7, 28), 65),
    ("Thriftle", "Back-to-Campus Fits", "Fashion Retail", "Conversions",
     4, ["Instagram", "TikTok"], date(2026, 8, 1), date(2026, 8, 31), 42),
    ("Wanderloop", "Book Fall Break Early", "Travel", "App Installs",
     5, ["Instagram"], date(2026, 6, 20), date(2026, 7, 25), 31),
    ("StackStart Financial", "Your First Credit Card, Minus the Trap", "Fintech", "Conversions",
     6, ["Instagram", "X (Twitter)"], date(2026, 7, 10), date(2026, 8, 31), 75),
    ("StadiumStash", "Game Day Delivered to Your Seat", "Food Delivery", "App Installs",
     7, ["Snapchat", "X (Twitter)"], date(2026, 8, 14), date(2026, 8, 31), 18),
    ("EchoPass Events", "Fall Fest Presale Access", "Live Events", "Traffic",
     8, ["TikTok", "Instagram"], date(2026, 7, 15), date(2026, 8, 20), 96),
    ("Calmello", "Beat the Syllabus Scaries", "Wellness Apps", "App Installs",
     9, ["Instagram", "TikTok"], date(2026, 8, 10), date(2026, 8, 31), 38),
    ("SwipeSaver", "Campus Deals All Summer", "Coupons & Deals", "Awareness",
     10, ["Snapchat", "TikTok"], date(2026, 6, 1), date(2026, 8, 31), 9),
    ("CreatorLoft", "Turn Followers Into Rent Money", "Creator Tools", "Conversions",
     11, ["Instagram", "X (Twitter)"], date(2026, 7, 1), date(2026, 8, 31), 144),
]

CONV_RATE = {"Conversions": 0.06, "App Installs": 0.09, "Traffic": 0.03, "Awareness": 0.012}

VALUES_SEGMENTS = ["Trendsetters", "Changemakers", "Achievers", "Experience Seekers",
                   "Belongers", "Pragmatists"]

DAYPARTS = ["Morning (6-10am)", "Midday (10am-2pm)", "Afternoon (2-6pm)",
            "Evening (6-10pm)", "Late Night (10pm-2am)"]


# ------------------------------------------------------------- generators ---
def gen_latents():
    lat = {
        "sociability": rng.betavariate(2.2, 2.0),
        "night_owl": rng.betavariate(2.4, 1.9),
        "video_affinity": rng.betavariate(2.6, 1.7),
        "shopper": rng.betavariate(2.0, 2.4),
        "athletic": rng.betavariate(1.9, 2.3),
        "gamer": rng.betavariate(1.7, 2.5),
        "aesthetic": rng.betavariate(2.0, 2.2),
        "foodie": rng.betavariate(2.3, 2.0),
        "techie": rng.betavariate(1.8, 2.4),
        "activist": rng.betavariate(1.7, 2.6),
        "wanderlust": rng.betavariate(2.1, 2.1),
        "finance_minded": rng.betavariate(1.6, 2.8),
        "music_fan": rng.betavariate(2.5, 1.8),
        "sports_fan": rng.betavariate(2.0, 2.2),
        "wellness": rng.betavariate(1.9, 2.3),
        "studious": rng.betavariate(2.0, 2.0),
    }
    raw_creator = rng.betavariate(1.6, 3.4)
    lat["creator"] = clamp(0.6 * raw_creator + 0.4 * lat["sociability"] + rng.gauss(0, 0.05))
    return lat


def gen_users():
    users = []
    used_emails = set()
    for i in range(1, N_USERS + 1):
        uid = f"U{i:04d}"
        gender = wchoice([("Female", 52), ("Male", 44), ("Non-binary", 3),
                          ("Prefer not to say", 1)])
        if gender == "Female":
            fn = rng.choice(FIRST_F)
        elif gender == "Male":
            fn = rng.choice(FIRST_M)
        else:
            fn = rng.choice(FIRST_N)
        ln = rng.choice(LAST)

        cy, _, base_age = rng.choices(
            [(c, w, a) for c, w, a in CLASS_YEARS],
            weights=[w for _, w, _ in CLASS_YEARS])[0]
        age = base_age + wchoice([(0, 60), (1, 30), (2, 8), (3, 2)])
        birth_year = 2026 - age
        birth = date(birth_year, rng.randint(1, 12), rng.randint(1, 28))

        uni, ucity, ustate, ulat, ulon, _ = rng.choices(
            UNIVERSITIES, weights=[u[5] for u in UNIVERSITIES])[0]

        if rng.random() < 0.68 and ustate in HOMETOWNS_BY_STATE:
            hcity, hlat, hlon = rng.choice(HOMETOWNS_BY_STATE[ustate])
            hstate = ustate
        else:
            hcity, hstate, hlat, hlon = rng.choice(HOMETOWNS_OTHER)

        n = 0
        while True:
            email = f"{fn.lower()}.{ln.lower()}{rng.randint(1, 999)}@example.edu"
            if email not in used_emails:
                used_emails.add(email)
                break
            n += 1
        area = str(rng.randint(201, 989))
        phone = f"({area}) 555-0{rng.randint(100, 199)}"  # reserved fictional range
        hashed = hashlib.md5(email.encode()).hexdigest()

        major = wchoice(MAJORS)
        housing = wchoice(HOUSING) if cy != "Graduate" else \
            wchoice([("Off-Campus Apartment", 70), ("University Apartment", 20),
                     ("Lives at Home", 10)])

        spend = round(clamp(rng.lognormvariate(5.35, 0.55), 60, 1500))
        lat = gen_latents()
        users.append(dict(
            user_id=uid, first_name=fn, last_name=ln, gender=gender, age=age,
            birth_date=birth.isoformat(), email=email, phone=phone,
            hashed_email=hashed, university=uni, campus_city=ucity,
            campus_state=ustate, campus_lat=ulat, campus_lon=ulon,
            housing=housing, class_year=cy, major=major, hometown_city=hcity,
            hometown_state=hstate, hometown_lat=hlat, hometown_lon=hlon,
            relationship=wchoice(RELATIONSHIP),
            part_time_job=rng.random() < 0.56, spend=spend, lat=lat,
        ))
    return users


def gen_profiles(users):
    """One row per user per adopted platform, with behavior baselines."""
    profiles = []
    handles = {p: set() for p in PLATFORM_ORDER}
    pid = 0
    for u in users:
        lat = u["lat"]
        adopted = []
        for p in PLATFORM_ORDER:
            cfg = PCFG[p]
            padopt = cfg["adopt"]
            if p == "TikTok":
                padopt += 0.10 * (lat["video_affinity"] - 0.5)
            elif p == "Snapchat":
                padopt += 0.08 * (lat["sociability"] - 0.5) - 0.030 * (u["age"] - 18)
            elif p == "X (Twitter)":
                padopt += 0.30 * ((lat["techie"] + lat["sports_fan"] + lat["activist"]) / 3 - 0.4)
            elif p == "Facebook":
                padopt += (0.18 if u["class_year"] == "Graduate" else 0) + 0.02 * (u["age"] - 18)
            if rng.random() < clamp(padopt, 0.02, 0.99):
                adopted.append(p)
        if not adopted:
            adopted = ["Instagram"]

        for p in adopted:
            cfg = PCFG[p]
            pid += 1
            # unique handle
            while True:
                style = rng.random()
                fn, ln = u["first_name"].lower(), u["last_name"].lower()
                if style < 0.3:
                    h = f"{fn}{ln[0]}{rng.randint(1, 999)}"
                elif style < 0.55:
                    h = f"{fn}.{ln}{rng.choice(['', str(rng.randint(1, 99))])}"
                elif style < 0.75:
                    h = f"its{fn}{rng.choice(['', 'x', 'o', str(rng.randint(1, 9))])}"
                else:
                    h = f"{fn}_{rng.choice(['gram', 'tv', 'official', 'x', str(2024 + rng.randint(0, 6))])}"
                if h not in handles[p]:
                    handles[p].add(h)
                    break

            um = clamp(math.exp(rng.gauss(0, 0.45)), 0.30, 3.2)
            if p == "Instagram":
                aff = 0.75 + 0.5 * lat["aesthetic"] + 0.30 * lat["sociability"]
                months = int(rng.triangular(12, 110, 60))
                followers = int(clamp(rng.lognormvariate(
                    5.6 + 1.8 * lat["creator"] + 0.7 * lat["sociability"], 0.9), 25, 250000))
                following = int(clamp(rng.lognormvariate(6.0, 0.5), 40, 3500))
            elif p == "TikTok":
                aff = 0.60 + 0.8 * lat["video_affinity"] + 0.25 * lat["night_owl"]
                months = int(rng.triangular(4, 84, 40))
                followers = int(clamp(rng.lognormvariate(
                    4.9 + 2.2 * lat["creator"], 1.2), 5, 400000))
                following = int(clamp(rng.lognormvariate(6.2, 0.6), 30, 4000))
            elif p == "Snapchat":
                aff = 0.70 + 0.6 * lat["sociability"] - 0.02 * (u["age"] - 18)
                months = int(rng.triangular(12, 120, 70))
                followers = int(rng.triangular(40, 950, 260))   # snap friends
                following = followers
            elif p == "X (Twitter)":
                aff = 0.55 + 0.6 * ((lat["techie"] + lat["activist"] + lat["sports_fan"]) / 3)
                months = int(rng.triangular(2, 96, 30))
                followers = int(clamp(rng.lognormvariate(3.9 + 1.2 * lat["creator"], 1.1), 2, 120000))
                following = int(clamp(rng.lognormvariate(5.5, 0.7), 20, 3000))
            else:  # Facebook
                aff = 0.70 + 0.02 * (u["age"] - 18) + 0.2 * lat["sociability"]
                months = int(rng.triangular(6, 130, 80))
                followers = int(rng.triangular(80, 1400, 420))  # fb friends
                following = followers

            base_minutes = clamp(cfg["base_min"] * um * aff, 3, 290)
            comp_base = clamp(rng.gauss(cfg["comp_mu"], cfg["comp_sd"]) / 100
                              + 0.06 * lat["video_affinity"], 0.08, 0.97)
            like_rate = clamp(rng.gauss(*cfg["like"]), 0.004, 0.22)
            ctr = clamp(rng.gauss(*cfg["ctr"]) * (0.6 + 0.9 * lat["shopper"]), 0.0008, 0.05)
            fwd_rate = (0.004 + 0.012 * lat["sociability"]) * cfg["fwd_mult"]
            p_active = clamp(cfg["p_active"] * (0.85 + 0.30 * rng.random()), 0.25, 0.98)
            ppw = round(clamp(rng.gammavariate(1 + 4 * lat["creator"], 0.8), 0, 25), 1)
            eng = round(clamp(rng.gauss(4.0 - math.log10(max(followers, 10)), 1.2)
                              + 4 * lat["creator"], 0.2, 15), 2)
            ln_share = clamp(0.05 + 0.45 * lat["night_owl"] + rng.gauss(0, 0.05), 0.02, 0.75)

            chron = lat["night_owl"]
            if chron > 0.66:
                daypart = "Late Night (10pm-2am)"
            elif chron < 0.33:
                daypart = wchoice([("Morning (6-10am)", 5), ("Midday (10am-2pm)", 3),
                                   ("Evening (6-10pm)", 2)])
            else:
                daypart = wchoice([("Evening (6-10pm)", 5), ("Afternoon (2-6pm)", 3),
                                   ("Midday (10am-2pm)", 2)])

            if p == "Snapchat":
                private = rng.random() < 0.85
            else:
                base_priv = {"Instagram": 0.34, "TikTok": 0.22,
                             "X (Twitter)": 0.18, "Facebook": 0.42}[p]
                private = rng.random() < clamp(base_priv + 0.20 * (1 - lat["sociability"]), 0.05, 0.9)

            profiles.append(dict(
                profile_id=f"P{pid:05d}", user_id=u["user_id"], platform=p,
                handle=h, months=months, followers=followers, following=following,
                eng=eng, ppw=ppw, base_minutes=base_minutes, daypart=daypart,
                private=private,
                verified=(followers > 20000 and rng.random() < 0.3),
                ads_on=rng.random() < clamp(0.78 - 0.25 * lat["activist"] - 0.10 * lat["techie"], 0.35, 0.95),
                loc_on=rng.random() < clamp({"Snapchat": 0.58, "Instagram": 0.32, "TikTok": 0.28,
                                             "X (Twitter)": 0.22, "Facebook": 0.38}[p]
                                            - 0.15 * lat["activist"], 0.05, 0.9),
                contacts=rng.random() < clamp(0.72 - 0.20 * lat["activist"] + 0.10 * lat["sociability"], 0.2, 0.95),
                comp_base=comp_base, like_rate=like_rate, ctr=ctr,
                fwd_rate=fwd_rate, p_active=p_active, ln_share=ln_share,
            ))
    return profiles


def gen_psychographics(users, prof_by_user):
    rows = []
    for u in users:
        lat = u["lat"]
        max_fol = max((p["followers"] for p in prof_by_user.get(u["user_id"], [])), default=0)
        fol_norm = clamp(math.log10(max(max_fol, 10)) / 5.5)
        openness = round(100 * clamp(0.30 * lat["aesthetic"] + 0.25 * lat["wanderlust"]
                                     + 0.20 * lat["techie"] + 0.25 * rng.random()))
        consc = round(100 * clamp(0.40 * lat["studious"] + 0.20 * (1 - lat["night_owl"])
                                  + 0.15 * lat["finance_minded"] + 0.25 * rng.random()))
        extra = round(100 * clamp(0.60 * lat["sociability"] + 0.15 * lat["creator"]
                                  + 0.25 * rng.random()))
        agree = round(100 * clamp(0.65 * rng.random() + 0.35 * lat["wellness"]))
        neuro = round(100 * clamp(0.30 * lat["night_owl"] + 0.55 * rng.random()))
        attention = round(100 * clamp(1 - 0.45 * lat["video_affinity"]
                                      - 0.20 * lat["night_owl"] + 0.30 * rng.random()))
        impulse = round(100 * clamp(0.70 * lat["shopper"] + 0.30 * rng.random()))
        influence = round(100 * clamp(0.45 * lat["creator"] + 0.25 * lat["sociability"]
                                      + 0.30 * fol_norm))

        c = lat["creator"]
        creator_level = ("Creator" if c > 0.72 else "Active Poster" if c > 0.55
                         else "Casual Poster" if c > 0.35 else "Lurker")
        chron = ("Night Owl" if lat["night_owl"] > 0.66
                 else "Early Bird" if lat["night_owl"] < 0.33 else "Flexible")

        vscores = {
            "Trendsetters": 0.6 * lat["aesthetic"] + 0.4 * lat["creator"],
            "Changemakers": lat["activist"],
            "Achievers": 0.5 * lat["finance_minded"] + 0.5 * lat["studious"],
            "Experience Seekers": 0.5 * lat["wanderlust"] + 0.5 * lat["music_fan"],
            "Belongers": 0.6 * lat["sociability"] + 0.4 * lat["wellness"],
            "Pragmatists": rng.uniform(0.3, 0.6),
        }
        vseg = max(vscores, key=vscores.get)

        # inferred political lean - deliberately included as a teaching point
        # about sensitive *inferred* attributes
        wts = {"Left": 22, "Center-Left": 26, "Center": 20,
               "Center-Right": 14, "Right": 10, "Not inferred": 8}
        if lat["activist"] > 0.7:
            wts["Left"] += 18
            wts["Center-Left"] += 8
        if lat["finance_minded"] > 0.72 and lat["activist"] < 0.4:
            wts["Center-Right"] += 10
            wts["Right"] += 6
        lean = wchoice(list(wts.items()))
        lean_conf = 0.0 if lean == "Not inferred" else round(rng.uniform(0.35, 0.95), 2)

        rows.append([
            u["user_id"], openness, consc, extra, agree, neuro, chron, attention,
            impulse, influence, creator_level, vseg, lean, lean_conf,
            b(rng.random() < 0.18 + 0.15 * lat["techie"]),
            b(rng.random() < 0.15 + 0.35 * lat["wanderlust"]),
            b(rng.random() < 0.20 + 0.30 * lat["foodie"]),
            b(rng.random() < 0.10 + 0.35 * lat["athletic"]),
            b(rng.random() < 0.08 + 0.30 * lat["finance_minded"]),
            b(rng.random() < 0.15),
        ])
    return rows


def gen_interests(users):
    dim_rows, bridge = [], []
    ids = {}
    for i, (name, cat, drv, w) in enumerate(INTEREST_DEFS, 1):
        iid = f"INT{i:02d}"
        ids[name] = (iid, drv, w)
        dim_rows.append([iid, name, cat])

    top_interest = {}
    for u in users:
        lat = u["lat"]
        scored = []
        for name, cat, drv, w in INTEREST_DEFS:
            iid = ids[name][0]
            if drv is None:
                score = rng.betavariate(1.2, 4.0)
            else:
                score = clamp(0.70 * (lat[drv] * (0.6 + w)) + 0.30 * rng.betavariate(1.4, 2.8))
            scored.append((score, iid))
        scored.sort(reverse=True)
        keep = [s for s in scored if s[0] > 0.42][:14]
        if len(keep) < 5:
            keep = scored[:5]
        top_interest[u["user_id"]] = keep[0][1]
        for score, iid in keep:
            src = wchoice([("Declared", 18), ("Engagement-inferred", 62),
                           ("Lookalike model", 20)])
            bridge.append([u["user_id"], iid, round(100 * score), src])
    return dim_rows, bridge, top_interest


def gen_segments(users, prof_by_user):
    seg_rows, bridge = [], []
    members = {}
    biz_majors = {"Finance", "Business Administration", "Economics", "Accounting",
                  "Marketing", "Information Systems"}
    # population average minutes per platform, for over-index calculation
    pop_min, pop_cnt = {}, {}
    for plist in prof_by_user.values():
        for p in plist:
            pop_min[p["platform"]] = pop_min.get(p["platform"], 0) + p["base_minutes"]
            pop_cnt[p["platform"]] = pop_cnt.get(p["platform"], 0) + 1
    pop_avg = {k: pop_min[k] / pop_cnt[k] for k in pop_min}
    for i, (name, tag, drv, thr, cpm, rule) in enumerate(SEGMENT_DEFS, 1):
        sid = f"SEG{i:02d}"
        mem = []
        for u in users:
            v = u["lat"][drv]
            qualifies = v > thr
            if name == "Budget Foodies":
                qualifies = qualifies and u["spend"] < 450
            elif name == "Money-Minded Strivers":
                qualifies = qualifies or (u["major"] in biz_majors and v > 0.45)
            elif name == "Micro-Influencers & Creators":
                max_fol = max((p["followers"] for p in prof_by_user.get(u["user_id"], [])),
                              default=0)
                qualifies = qualifies or max_fol >= 8000
            if qualifies:
                strength = round(clamp(40 + 60 * (v - thr) / (1 - thr), 25, 100))
                mem.append((u["user_id"], strength))
                bridge.append([u["user_id"], sid, strength])
        members[sid] = mem

        # platform where members OVER-INDEX vs the general student population
        plat_min, plat_cnt = {}, {}
        mem_ids = {m[0] for m in mem}
        for uid in mem_ids:
            for p in prof_by_user.get(uid, []):
                plat_min[p["platform"]] = plat_min.get(p["platform"], 0) + p["base_minutes"]
                plat_cnt[p["platform"]] = plat_cnt.get(p["platform"], 0) + 1
        # over-index ratio, damped by how many members are actually there
        ratios = {k: ((plat_min[k] / plat_cnt[k]) / pop_avg[k])
                  * (0.5 + 0.5 * plat_cnt[k] / max(len(mem), 1))
                  for k in plat_min if plat_cnt[k] >= 20}
        top_plat = max(ratios, key=ratios.get) if ratios else "Instagram"
        avg_str = round(sum(m[1] for m in mem) / max(len(mem), 1), 1)
        seg_rows.append([sid, name, tag, rule, len(mem), avg_str, top_plat, f"{cpm:.2f}"])
    return seg_rows, bridge, members


def gen_devices(users, total_min_by_user):
    rows = []
    did = 0
    for u in users:
        lat = u["lat"]
        tmin = total_min_by_user.get(u["user_id"], 120)
        did += 1
        brand = wchoice([("Apple", 74), ("Samsung", 17), ("Google", 6), ("Motorola", 3)])
        if brand == "Apple":
            model = wchoice([("iPhone 17", 10), ("iPhone 16", 22), ("iPhone 15", 26),
                             ("iPhone 14", 20), ("iPhone 13", 14), ("iPhone Air", 8)])
            os_v = "iOS 26.1" if rng.random() < 0.8 else "iOS 18.6"
            track = rng.random() < 0.27  # App Tracking Transparency opt-in
        else:
            if brand == "Samsung":
                model = wchoice([("Galaxy S25", 30), ("Galaxy S24", 30),
                                 ("Galaxy S23", 15), ("Galaxy A56", 25)])
            elif brand == "Google":
                model = wchoice([("Pixel 10", 35), ("Pixel 9", 40), ("Pixel 8a", 25)])
            else:
                model = wchoice([("Moto G Power", 60), ("Motorola Edge", 40)])
            os_v = "Android 16" if rng.random() < 0.7 else "Android 15"
            track = rng.random() < 0.80  # Android default-on unless limited
        pickups = round(clamp(rng.gauss(70 + 60 * (tmin / 220), 24), 20, 230))
        wifi = round(clamp(rng.gauss(0.62, 0.12), 0.2, 0.95) * 100)
        carrier = wchoice([("Verizon", 30), ("T-Mobile", 27), ("AT&T", 26),
                           ("Mint Mobile", 6), ("Visible", 5), ("Cricket", 4),
                           ("US Cellular", 2)])
        rows.append([f"DEV{did:05d}", u["user_id"], "Smartphone", brand, model, os_v,
                     "TRUE", fake_uuid(), b(track), pickups, wifi, carrier])

        if rng.random() < 0.80:
            did += 1
            if rng.random() < 0.60:
                lmodel, los = wchoice([("MacBook Air", 65), ("MacBook Pro", 35)]), "macOS 26"
                lbrand = "Apple"
            else:
                if lat["gamer"] > 0.7 and rng.random() < 0.5:
                    lbrand, lmodel = wchoice([("ASUS", 55), ("Lenovo", 45)]), "Gaming Laptop"
                else:
                    lbrand = wchoice([("Dell", 30), ("HP", 28), ("Lenovo", 24), ("Microsoft", 18)])
                    lmodel = {"Dell": "XPS 13", "HP": "Spectre x360",
                              "Lenovo": "Yoga Slim", "Microsoft": "Surface Laptop"}[lbrand]
                los = "Windows 11"
            rows.append([f"DEV{did:05d}", u["user_id"], "Laptop", lbrand, lmodel, los,
                         "FALSE", "", "", "", round(clamp(rng.gauss(0.88, 0.08), 0.5, 1) * 100), ""])
        if rng.random() < 0.27:
            did += 1
            if rng.random() < 0.85:
                tb, tm, tos = "Apple", wchoice([("iPad", 50), ("iPad Air", 30), ("iPad Pro", 20)]), "iPadOS 26"
            else:
                tb, tm, tos = "Samsung", "Galaxy Tab S9", "Android 16"
            rows.append([f"DEV{did:05d}", u["user_id"], "Tablet", tb, tm, tos,
                         "FALSE", "", "", "", round(clamp(rng.gauss(0.9, 0.07), 0.5, 1) * 100), ""])
    return rows


def build_dates():
    dates = []
    d = START_DATE
    while d <= END_DATE:
        dates.append(dict(
            iso=d.isoformat(), d=d, weekend=d.weekday() >= 5,
            post_sem=d >= SEMESTER_START, weekday=d.weekday(),
        ))
        d += timedelta(days=1)
    return dates


def gen_engagement(profiles, dates, path):
    """Streams the big daily fact straight to disk; returns per-user expected
    total daily minutes (for devices + hourly usage) and row count."""
    total_min = {}
    n_rows = 0
    header = ["activity_date", "user_id", "platform", "active_minutes", "sessions",
              "posts_viewed", "videos_viewed", "avg_video_completion_pct",
              "videos_forwarded", "likes_given", "comments_written", "posts_created",
              "stories_viewed", "ads_seen", "ads_clicked", "late_night_minutes"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for pr in profiles:
            cfg = PCFG[pr["platform"]]
            uid = pr["user_id"]
            total_min[uid] = total_min.get(uid, 0) + pr["base_minutes"] * pr["p_active"]
            for day in dates:
                if rng.random() > pr["p_active"]:
                    continue
                mult = cfg["wkend"] if day["weekend"] else 1.0
                if day["post_sem"]:
                    mult *= 0.93
                minutes = pr["base_minutes"] * mult * math.exp(rng.gauss(0, 0.35))
                minutes = int(clamp(minutes, 2, 420))
                sessions = max(1, round(minutes / cfg["sess_len"] * rng.uniform(0.8, 1.25)))
                posts = int(minutes * cfg["cpm_content"] * rng.uniform(0.8, 1.2))
                videos = int(posts * cfg["video_share"] * rng.uniform(0.85, 1.15))
                comp = clamp(pr["comp_base"] + rng.gauss(0, 0.05), 0.05, 0.99)
                fwd = frac_int(videos * pr["fwd_rate"], cap=40)
                likes = int(posts * pr["like_rate"] * rng.uniform(0.7, 1.3))
                comments = frac_int(likes * 0.08, cap=30)
                created = frac_int(pr["ppw"] / 7 * (1.4 if day["weekend"] else 1.0), cap=6)
                if cfg["story"]:
                    stories = int(minutes * 1.5 * rng.uniform(0.6, 1.4))
                else:
                    stories = 0
                ads = frac_int(posts * cfg["ad_load"])
                clicks = frac_int(ads * pr["ctr"], cap=ads)
                ln_share = pr["ln_share"] + (0.06 if day["post_sem"] else 0)
                late = int(minutes * clamp(ln_share, 0, 0.8))
                w.writerow([day["iso"], uid, pr["platform"], minutes, sessions,
                            posts, videos, round(100 * comp, 1), fwd, likes,
                            comments, created, stories, ads, clicks, late])
                n_rows += 1
    return total_min, n_rows


def circ_bump(h, mu, sd):
    d = abs(h - mu)
    d = min(d, 24 - d)
    return math.exp(-((d / sd) ** 2))


def gen_hourly(users, total_min_by_user):
    rows = []
    for u in users:
        no = u["lat"]["night_owl"]
        total = total_min_by_user.get(u["user_id"], 100)
        peak_evening = 19.5 + 4.0 * no
        weights = []
        for h in range(24):
            v = 0.02
            v += circ_bump(h, 8.0, 1.5) * (0.55 if no < 0.33 else 0.20)
            v += circ_bump(h, 12.5, 1.6) * 0.35
            v += circ_bump(h, 17.0, 2.2) * 0.45
            v += circ_bump(h, peak_evening, 2.3) * 1.10
            v += circ_bump(h, 0.8, 1.7) * (1.05 * no)
            if 3 <= h <= 5:
                v *= 0.15
            weights.append(v)
        s = sum(weights)
        for day_type, mult in (("Weekday", 0.96), ("Weekend", 1.10)):
            day_total = total * mult
            for h in range(24):
                rows.append([u["user_id"], day_type, h,
                             round(day_total * weights[h] / s, 1)])
    return rows


def gen_campaigns(users_by_id, prof_by_user, seg_members, dates):
    """fact_ad_exposures is what happened to the 2,000-student research panel.
    fact_campaign_daily is the FULL campaign delivery: each panel member stands
    for `panel_scale_factor` students in the campaign's total audience, so the
    daily table equals the panel totals x that factor, exactly."""
    camp_rows, exposures, daily = [], [], []
    for i, (brand, cname, vertical, objective, seg_idx, plats, fstart, fend, aov) \
            in enumerate(CAMPAIGN_DEFS, 1):
        cid = f"CMP{i:02d}"
        sid = f"SEG{seg_idx + 1:02d}"
        seg_cpm = float(SEGMENT_DEFS[seg_idx][4])
        flight_days = [d for d in dates if fstart <= d["d"] <= fend]
        n_days = len(flight_days)
        ctr_base = rng.uniform(0.005, 0.013)
        conv_rate = CONV_RATE[objective]
        factor = rng.randrange(250, 601, 50)  # students represented per panel member

        # per-user exposures (only segment members with an ads-on profile)
        camp_expo = []
        for uid, strength in seg_members[sid]:
            u = users_by_id[uid]
            for p in plats:
                prof = next((x for x in prof_by_user.get(uid, []) if x["platform"] == p), None)
                if prof is None or not prof["ads_on"]:
                    continue
                if rng.random() > 0.62:
                    continue
                freq = rng.uniform(1.2, 3.5)  # paid-social frequency per day
                imps = max(2, min(240, int(n_days * freq * math.exp(rng.gauss(0, 0.4)))))
                ctr_u = clamp(ctr_base * (0.5 + 0.9 * u["lat"]["shopper"]
                                          + 0.5 * strength / 100), 0.0008, 0.045)
                clicks = min(imps, frac_int(imps * ctr_u))
                vcomp = int(imps * rng.uniform(0.30, 0.55)) if p != "X (Twitter)" else \
                    int(imps * rng.uniform(0.08, 0.2))
                conv = frac_int(clicks * conv_rate + imps * 0.00015, cap=2)
                i0 = rng.randint(0, n_days - 1)
                i1 = rng.randint(i0, n_days - 1)
                camp_expo.append([uid, cid, p, imps, clicks, vcomp, conv,
                                  flight_days[i0]["iso"], flight_days[i1]["iso"]])
        exposures.extend(camp_expo)

        # full-scale daily rollup - reconciles exactly with exposures x factor
        total_spend = 0.0
        for p in plats:
            rows_p = [e for e in camp_expo if e[2] == p]
            t_imp = sum(e[3] for e in rows_p) * factor
            t_clk = sum(e[4] for e in rows_p) * factor
            t_vc = sum(e[5] for e in rows_p) * factor
            t_cnv = sum(e[6] for e in rows_p) * factor
            wts = []
            for j, day in enumerate(flight_days):
                ramp = 0.55 + 0.9 * min(1.0, j / 6.0)
                wk = 1.10 if (day["weekend"] and p in ("TikTok", "Snapchat")) else \
                    (0.95 if day["weekend"] else 1.0)
                wts.append(ramp * wk * math.exp(rng.gauss(0, 0.18)))
            d_imp = allocate(t_imp, wts)
            d_clk = allocate(t_clk, wts)
            d_vc = allocate(t_vc, wts)
            d_cnv = allocate(t_cnv, wts)
            cpm = PCFG[p]["cpm_usd"] * rng.uniform(0.85, 1.2) * (seg_cpm / 9.0)
            for j, day in enumerate(flight_days):
                spend = round(d_imp[j] / 1000 * cpm, 2)
                revenue = round(d_cnv[j] * aov * rng.uniform(0.9, 1.15), 2)
                total_spend += spend
                daily.append([day["iso"], cid, p, d_imp[j], d_clk[j], d_vc[j],
                              d_cnv[j], f"{spend:.2f}", f"{revenue:.2f}"])

        budget = max(100.0, round(total_spend * rng.uniform(1.03, 1.20), -2))
        t_imp_all = sum(e[3] for e in camp_expo) * factor
        avg_cpm = round(total_spend / max(t_imp_all, 1) * 1000, 2)
        status = "Completed" if fend < END_DATE else "Live"
        camp_rows.append([cid, brand, cname, vertical, objective, sid,
                          "; ".join(plats), fstart.isoformat(), fend.isoformat(),
                          f"{budget:.2f}", f"{total_spend:.2f}", f"{avg_cpm:.2f}",
                          f"{aov:.2f}", factor, status])
    return camp_rows, exposures, daily


def gen_connections(users, prof_by_user, top_interest):
    by_uni = {}
    by_interest = {}
    for u in users:
        by_uni.setdefault(u["university"], []).append(u["user_id"])
        by_interest.setdefault(top_interest[u["user_id"]], []).append(u["user_id"])
    users_by_id = {u["user_id"]: u for u in users}
    all_ids = [u["user_id"] for u in users]
    pairs = set()
    edges = []
    conn_type = {"Instagram": "Mutual follow", "TikTok": "Mutual follow",
                 "Snapchat": "Snap friends", "X (Twitter)": "Mutual follow",
                 "Facebook": "Facebook friends"}
    for u in users:
        uid = u["user_id"]
        degree = int(clamp(rng.gauss(6 + 10 * u["lat"]["sociability"], 3), 2, 26))
        my_plats = {p["platform"] for p in prof_by_user.get(uid, [])}
        attempts = 0
        made = 0
        while made < degree and attempts < degree * 6:
            attempts += 1
            r = rng.random()
            if r < 0.75:
                pool = by_uni[u["university"]]
            elif r < 0.90:
                pool = by_interest.get(top_interest[uid], all_ids)
            else:
                pool = all_ids
            other = rng.choice(pool)
            if other == uid:
                continue
            key = (min(uid, other), max(uid, other))
            if key in pairs:
                continue
            other_plats = {p["platform"] for p in prof_by_user.get(other, [])}
            common = [p for p in PLATFORM_ORDER if p in my_plats and p in other_plats]
            if not common:
                continue
            plat = rng.choices(common, weights=[
                {"Instagram": 5, "Snapchat": 4, "TikTok": 2.5,
                 "X (Twitter)": 1, "Facebook": 1.5}[c] for c in common])[0]
            pairs.add(key)
            same_uni = users_by_id[other]["university"] == u["university"]
            same_int = top_interest[other] == top_interest[uid]
            strength = round(clamp(rng.betavariate(2, 4) + (0.20 if same_uni else 0), 0.03, 1.0), 3)
            edges.append((uid, other, plat, conn_type[plat], strength, same_uni, same_int))
            made += 1
    rows = []
    for a, o, plat, ct, s, su, si in edges:   # mirror both directions
        rows.append([a, o, plat, ct, s, b(su), b(si)])
        rows.append([o, a, plat, ct, s, b(su), b(si)])
    return rows


def gen_dim_date(dates):
    rows = []
    for day in dates:
        d = day["d"]
        rows.append([day["iso"], d.year, d.month, d.strftime("%B"),
                     d.isocalendar()[1], d.weekday() + 1, d.strftime("%A"),
                     b(day["weekend"]),
                     "Fall Semester" if day["post_sem"] else "Summer Break"])
    return rows


# ---------------------------------------------------------- data dictionary --
def dictionary_rows():
    D, O, I, V, P = ("Declared by user", "Observed behavior", "Inferred by model",
                     "Derived / packaged", "Platform metadata")
    rows = []

    def add(table, entries):
        for col, dtype, desc, method, sens in entries:
            rows.append([table, col, dtype, desc, method, sens])

    add("dim_users", [
        ("user_id", "text", "Unique synthetic person ID; joins to every other table", V, "Low"),
        ("first_name", "text", "First name provided at signup", D, "High"),
        ("last_name", "text", "Last name provided at signup", D, "High"),
        ("gender", "text", "Self-reported gender", D, "Medium"),
        ("age", "int", "Age in years, from date of birth", D, "Medium"),
        ("birth_date", "date", "Date of birth provided at signup", D, "High"),
        ("email", "text", "Signup email address (fake @example.edu)", D, "High"),
        ("phone", "text", "Phone number on file (fictional 555 range)", D, "High"),
        ("hashed_email", "text", "MD5 of email - how identity is matched between ad systems", V, "High"),
        ("university", "text", "School attended, from profile + geo signals", I, "Medium"),
        ("campus_city", "text", "City of campus", I, "Medium"),
        ("campus_state", "text", "State of campus", I, "Medium"),
        ("campus_lat", "decimal", "Campus latitude for mapping", I, "High"),
        ("campus_lon", "decimal", "Campus longitude for mapping", I, "High"),
        ("housing_type", "text", "Dorm / apartment / at home, inferred from location patterns", I, "High"),
        ("class_year", "text", "Freshman through Graduate", I, "Low"),
        ("major", "text", "Field of study, from bio text and page follows", I, "Medium"),
        ("hometown_city", "text", "Hometown from profile and holiday location patterns", I, "Medium"),
        ("hometown_state", "text", "Hometown state", I, "Medium"),
        ("hometown_lat", "decimal", "Hometown latitude", I, "High"),
        ("hometown_lon", "decimal", "Hometown longitude", I, "High"),
        ("relationship_status", "text", "Declared or inferred relationship status", I, "High"),
        ("has_part_time_job", "bool", "Employment signal from activity patterns", I, "Medium"),
        ("est_monthly_discretionary_spend_usd", "int", "Modeled spending power", I, "High"),
    ])
    add("dim_psychographics", [
        ("user_id", "text", "Joins to dim_users", V, "Low"),
        ("openness", "int 0-100", "Big Five: openness to experience", I, "High"),
        ("conscientiousness", "int 0-100", "Big Five: conscientiousness", I, "High"),
        ("extraversion", "int 0-100", "Big Five: extraversion", I, "High"),
        ("agreeableness", "int 0-100", "Big Five: agreeableness", I, "High"),
        ("neuroticism", "int 0-100", "Big Five: neuroticism", I, "High"),
        ("chronotype", "text", "Early Bird / Flexible / Night Owl from usage times", I, "Medium"),
        ("attention_span_score", "int 0-100", "Modeled from scroll speed and completion rates", I, "Medium"),
        ("impulse_buying_score", "int 0-100", "Modeled from ad-click and checkout behavior", I, "High"),
        ("social_influence_score", "int 0-100", "How much this person sways their network", I, "Medium"),
        ("content_creator_level", "text", "Lurker / Casual / Active / Creator", O, "Low"),
        ("values_segment", "text", "Marketing values archetype", I, "Medium"),
        ("inferred_political_lean", "text", "Political leaning inferred from follows and engagement", I, "High"),
        ("political_lean_confidence", "decimal 0-1", "Model confidence in the political inference", I, "High"),
        ("intent_new_phone", "bool", "In-market signal: shopping for a phone", I, "Medium"),
        ("intent_travel_6mo", "bool", "In-market signal: planning travel", I, "Medium"),
        ("intent_meal_delivery", "bool", "In-market signal: food delivery", I, "Medium"),
        ("intent_gym_membership", "bool", "In-market signal: fitness services", I, "Medium"),
        ("intent_credit_card", "bool", "In-market signal: first credit card", I, "High"),
        ("recently_moved", "bool", "Life event flag from address/geo change", I, "High"),
    ])
    add("dim_platforms", [
        ("platform", "text", "Platform name; joins to profiles and facts", P, "Low"),
        ("parent_company", "text", "Owning company (note Meta owns two of the five)", P, "Low"),
        ("headquarters", "text", "Company HQ location", P, "Low"),
        ("year_launched", "int", "Year the platform launched", P, "Low"),
        ("primary_content_format", "text", "Dominant content type", P, "Low"),
        ("privacy_policy_url", "text", "Real privacy policy for classroom reference", P, "Low"),
    ])
    add("dim_platform_profiles", [
        ("profile_id", "text", "Unique account ID", V, "Low"),
        ("user_id", "text", "Joins to dim_users", V, "Low"),
        ("platform", "text", "Which platform this account is on", P, "Low"),
        ("handle", "text", "Public username", D, "Medium"),
        ("account_age_months", "int", "How long the account has existed", P, "Low"),
        ("follower_count", "int", "Followers (friend count on Snapchat/Facebook)", O, "Low"),
        ("following_count", "int", "Accounts followed", O, "Low"),
        ("engagement_rate_pct", "decimal", "Avg engagements per follower per post", O, "Low"),
        ("posts_per_week", "decimal", "Posting frequency", O, "Low"),
        ("avg_daily_minutes", "decimal", "Typical minutes per active day", O, "Medium"),
        ("primary_usage_daypart", "text", "When this account is most active", O, "Medium"),
        ("is_private_account", "bool", "Whether the account is private", D, "Low"),
        ("verified", "bool", "Verification badge", P, "Low"),
        ("ad_personalization_enabled", "bool", "User left personalized ads ON", D, "Medium"),
        ("location_sharing_enabled", "bool", "Precise location shared with the app", D, "High"),
        ("contacts_synced", "bool", "Phone contact list uploaded to the platform", D, "High"),
    ])
    add("dim_devices", [
        ("device_id", "text", "Unique device ID", V, "Low"),
        ("user_id", "text", "Joins to dim_users", V, "Low"),
        ("device_type", "text", "Smartphone / Laptop / Tablet", O, "Low"),
        ("brand", "text", "Device manufacturer", O, "Low"),
        ("model", "text", "Device model", O, "Low"),
        ("operating_system", "text", "OS and version", O, "Low"),
        ("is_primary_device", "bool", "Main device used for social apps", O, "Low"),
        ("mobile_advertising_id", "text", "IDFA/GAID-style ad identifier (phones only)", P, "High"),
        ("ad_tracking_allowed", "bool", "Cross-app tracking permitted (ATT opt-in on iOS)", D, "High"),
        ("avg_daily_pickups", "int", "Times per day the phone is picked up", O, "Medium"),
        ("pct_time_on_wifi", "int", "Share of usage on Wi-Fi vs cellular", O, "Low"),
        ("carrier", "text", "Mobile carrier (phones only)", P, "Medium"),
    ])
    add("dim_interests", [
        ("interest_id", "text", "Interest taxonomy ID", V, "Low"),
        ("interest_name", "text", "Interest label, like real ad-platform targeting categories", V, "Low"),
        ("interest_category", "text", "Taxonomy grouping", V, "Low"),
    ])
    add("bridge_user_interests", [
        ("user_id", "text", "Joins to dim_users", V, "Low"),
        ("interest_id", "text", "Joins to dim_interests", V, "Low"),
        ("affinity_score", "int 0-100", "Strength of the interest signal", I, "Medium"),
        ("source", "text", "Declared vs engagement-inferred vs lookalike model", V, "Medium"),
    ])
    add("dim_segments", [
        ("segment_id", "text", "Packaged audience segment ID", V, "Low"),
        ("segment_name", "text", "Name CampusPulse sells this audience under", V, "Low"),
        ("tagline", "text", "Sales pitch shown to advertisers", V, "Low"),
        ("membership_rule", "text", "Plain-language qualification rule", V, "Low"),
        ("member_count", "int", "Students currently in the segment", V, "Low"),
        ("avg_match_strength", "decimal", "Average membership strength (0-100)", V, "Low"),
        ("top_platform", "text", "Where this segment spends the most time", V, "Low"),
        ("suggested_cpm_usd", "decimal", "Price per 1,000 impressions we charge", V, "Low"),
    ])
    add("bridge_user_segments", [
        ("user_id", "text", "Joins to dim_users", V, "Low"),
        ("segment_id", "text", "Joins to dim_segments", V, "Low"),
        ("match_strength", "int 0-100", "How strongly the student fits the segment", V, "Medium"),
    ])
    add("dim_campaigns", [
        ("campaign_id", "text", "Ad campaign ID", V, "Low"),
        ("advertiser_brand", "text", "Fictional advertiser who bought the audience", V, "Low"),
        ("campaign_name", "text", "Campaign name", V, "Low"),
        ("advertiser_vertical", "text", "Advertiser industry", V, "Low"),
        ("objective", "text", "Awareness / Traffic / Conversions / App Installs", V, "Low"),
        ("primary_segment_id", "text", "Segment the campaign targeted; joins to dim_segments", V, "Low"),
        ("platforms", "text", "Platforms the campaign ran on (display only)", V, "Low"),
        ("flight_start", "date", "First day of the campaign", V, "Low"),
        ("flight_end", "date", "Last day of the campaign", V, "Low"),
        ("total_budget_usd", "decimal", "Budget the advertiser committed", V, "Low"),
        ("total_spend_usd", "decimal", "Actual delivered spend (full campaign)", V, "Low"),
        ("avg_cpm_usd", "decimal", "Realized cost per 1,000 impressions", V, "Low"),
        ("avg_order_value_usd", "decimal", "Average value of one conversion", V, "Low"),
        ("panel_scale_factor", "int", "Students in the full audience represented by each panel member", V, "Low"),
        ("status", "text", "Completed or Live as of Aug 31, 2026", V, "Low"),
    ])
    add("fact_engagement_daily", [
        ("activity_date", "date", "Day of activity; joins to dim_date", O, "Low"),
        ("user_id", "text", "Joins to dim_users", V, "Low"),
        ("platform", "text", "Joins to dim_platforms", P, "Low"),
        ("active_minutes", "int", "Minutes in the app that day", O, "Medium"),
        ("sessions", "int", "Times the app was opened", O, "Medium"),
        ("posts_viewed", "int", "Pieces of content served", O, "Medium"),
        ("videos_viewed", "int", "Videos among the content served", O, "Medium"),
        ("avg_video_completion_pct", "decimal", "Average % of each video watched", O, "Medium"),
        ("videos_forwarded", "int", "Videos shared/forwarded to others", O, "Medium"),
        ("likes_given", "int", "Likes/reactions given", O, "Medium"),
        ("comments_written", "int", "Comments posted", O, "Medium"),
        ("posts_created", "int", "Original posts published", O, "Low"),
        ("stories_viewed", "int", "Stories viewed (0 on platforms without stories)", O, "Medium"),
        ("ads_seen", "int", "Ads served that day (all advertisers)", O, "Medium"),
        ("ads_clicked", "int", "Ads clicked that day", O, "High"),
        ("late_night_minutes", "int", "Minutes between 10 p.m. and 2 a.m.", O, "High"),
    ])
    add("fact_hourly_usage", [
        ("user_id", "text", "Joins to dim_users", V, "Low"),
        ("day_type", "text", "Weekday or Weekend profile", V, "Low"),
        ("hour_of_day", "int 0-23", "Hour of the day", O, "Low"),
        ("avg_minutes", "decimal", "Typical minutes online in that hour (all platforms)", O, "High"),
    ])
    add("fact_ad_exposures", [
        ("user_id", "text", "Panel member who saw the ads; joins to dim_users", O, "High"),
        ("campaign_id", "text", "Joins to dim_campaigns", V, "Low"),
        ("platform", "text", "Where the ads were shown", P, "Low"),
        ("impressions", "int", "Ads from this campaign shown to this person", O, "High"),
        ("clicks", "int", "Times this person clicked the campaign", O, "High"),
        ("video_completions", "int", "Campaign videos watched to completion", O, "Medium"),
        ("conversions", "int", "Purchases/installs attributed to this person", O, "High"),
        ("first_exposure_date", "date", "First time the person saw the campaign", O, "Medium"),
        ("last_exposure_date", "date", "Most recent exposure", O, "Medium"),
    ])
    add("fact_campaign_daily", [
        ("activity_date", "date", "Delivery day; joins to dim_date", V, "Low"),
        ("campaign_id", "text", "Joins to dim_campaigns", V, "Low"),
        ("platform", "text", "Joins to dim_platforms", V, "Low"),
        ("impressions", "int", "Impressions delivered that day (full campaign = panel x scale factor)", V, "Low"),
        ("clicks", "int", "Clicks that day", V, "Low"),
        ("video_completions", "int", "Completed video views that day", V, "Low"),
        ("conversions", "int", "Attributed conversions that day", V, "Low"),
        ("spend_usd", "decimal", "Ad spend that day", V, "Low"),
        ("revenue_usd", "decimal", "Attributed revenue that day", V, "Low"),
    ])
    add("fact_connections", [
        ("user_id", "text", "Person A; joins to dim_users", O, "High"),
        ("connected_user_id", "text", "Person B (each friendship appears in both directions)", O, "High"),
        ("platform", "text", "Where the connection exists", P, "Low"),
        ("connection_type", "text", "Mutual follow / Snap friends / Facebook friends", O, "Low"),
        ("interaction_strength", "decimal 0-1", "How often the two interact", O, "High"),
        ("same_university", "bool", "Both attend the same school", I, "Medium"),
        ("shared_top_interest", "bool", "Both share the same #1 interest", I, "Medium"),
    ])
    add("dim_date", [
        ("date", "date", "Calendar date (Jun 1 - Aug 31, 2026)", V, "Low"),
        ("year", "int", "Year", V, "Low"),
        ("month_num", "int", "Month number for sorting", V, "Low"),
        ("month_name", "text", "Month name", V, "Low"),
        ("week_of_year", "int", "ISO week number", V, "Low"),
        ("day_of_week_num", "int 1-7", "Monday=1 for sorting", V, "Low"),
        ("day_name", "text", "Day of week", V, "Low"),
        ("is_weekend", "bool", "Saturday or Sunday", V, "Low"),
        ("academic_period", "text", "Summer Break vs Fall Semester (starts Aug 24)", V, "Low"),
    ])
    return rows


# ------------------------------------------------------------------- main ----
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Generating CampusPulse synthetic dataset (seed={SEED}, users={N_USERS})")

    dates = build_dates()
    users = gen_users()
    profiles = gen_profiles(users)
    prof_by_user = {}
    for p in profiles:
        prof_by_user.setdefault(p["user_id"], []).append(p)
    users_by_id = {u["user_id"]: u for u in users}

    counts = {}

    rows = [[u["user_id"], u["first_name"], u["last_name"], u["gender"], u["age"],
             u["birth_date"], u["email"], u["phone"], u["hashed_email"],
             u["university"], u["campus_city"], u["campus_state"], u["campus_lat"],
             u["campus_lon"], u["housing"], u["class_year"], u["major"],
             u["hometown_city"], u["hometown_state"], u["hometown_lat"],
             u["hometown_lon"], u["relationship"], b(u["part_time_job"]), u["spend"]]
            for u in users]
    write_csv("dim_users.csv",
              ["user_id", "first_name", "last_name", "gender", "age", "birth_date",
               "email", "phone", "hashed_email", "university", "campus_city",
               "campus_state", "campus_lat", "campus_lon", "housing_type",
               "class_year", "major", "hometown_city", "hometown_state",
               "hometown_lat", "hometown_lon", "relationship_status",
               "has_part_time_job", "est_monthly_discretionary_spend_usd"], rows)
    counts["dim_users"] = len(rows)

    rows = gen_psychographics(users, prof_by_user)
    write_csv("dim_psychographics.csv",
              ["user_id", "openness", "conscientiousness", "extraversion",
               "agreeableness", "neuroticism", "chronotype", "attention_span_score",
               "impulse_buying_score", "social_influence_score",
               "content_creator_level", "values_segment", "inferred_political_lean",
               "political_lean_confidence", "intent_new_phone", "intent_travel_6mo",
               "intent_meal_delivery", "intent_gym_membership", "intent_credit_card",
               "recently_moved"], rows)
    counts["dim_psychographics"] = len(rows)

    write_csv("dim_platforms.csv",
              ["platform", "parent_company", "headquarters", "year_launched",
               "primary_content_format", "privacy_policy_url"],
              [list(r) for r in PLATFORM_INFO])
    counts["dim_platforms"] = len(PLATFORM_INFO)

    rows = [[p["profile_id"], p["user_id"], p["platform"], p["handle"], p["months"],
             p["followers"], p["following"], p["eng"], p["ppw"],
             round(p["base_minutes"], 1), p["daypart"], b(p["private"]),
             b(p["verified"]), b(p["ads_on"]), b(p["loc_on"]), b(p["contacts"])]
            for p in profiles]
    write_csv("dim_platform_profiles.csv",
              ["profile_id", "user_id", "platform", "handle", "account_age_months",
               "follower_count", "following_count", "engagement_rate_pct",
               "posts_per_week", "avg_daily_minutes", "primary_usage_daypart",
               "is_private_account", "verified", "ad_personalization_enabled",
               "location_sharing_enabled", "contacts_synced"], rows)
    counts["dim_platform_profiles"] = len(rows)

    int_dim, int_bridge, top_interest = gen_interests(users)
    write_csv("dim_interests.csv",
              ["interest_id", "interest_name", "interest_category"], int_dim)
    write_csv("bridge_user_interests.csv",
              ["user_id", "interest_id", "affinity_score", "source"], int_bridge)
    counts["dim_interests"] = len(int_dim)
    counts["bridge_user_interests"] = len(int_bridge)

    seg_dim, seg_bridge, seg_members = gen_segments(users, prof_by_user)
    write_csv("dim_segments.csv",
              ["segment_id", "segment_name", "tagline", "membership_rule",
               "member_count", "avg_match_strength", "top_platform",
               "suggested_cpm_usd"], seg_dim)
    write_csv("bridge_user_segments.csv",
              ["user_id", "segment_id", "match_strength"], seg_bridge)
    counts["dim_segments"] = len(seg_dim)
    counts["bridge_user_segments"] = len(seg_bridge)

    print("  writing fact_engagement_daily (largest file)...")
    total_min, n_eng = gen_engagement(
        profiles, dates, os.path.join(OUT_DIR, "fact_engagement_daily.csv"))
    counts["fact_engagement_daily"] = n_eng

    rows = gen_devices(users, total_min)
    write_csv("dim_devices.csv",
              ["device_id", "user_id", "device_type", "brand", "model",
               "operating_system", "is_primary_device", "mobile_advertising_id",
               "ad_tracking_allowed", "avg_daily_pickups", "pct_time_on_wifi",
               "carrier"], rows)
    counts["dim_devices"] = len(rows)

    rows = gen_hourly(users, total_min)
    write_csv("fact_hourly_usage.csv",
              ["user_id", "day_type", "hour_of_day", "avg_minutes"], rows)
    counts["fact_hourly_usage"] = len(rows)

    camp_rows, exposures, camp_daily = gen_campaigns(
        users_by_id, prof_by_user, seg_members, dates)
    write_csv("dim_campaigns.csv",
              ["campaign_id", "advertiser_brand", "campaign_name",
               "advertiser_vertical", "objective", "primary_segment_id", "platforms",
               "flight_start", "flight_end", "total_budget_usd", "total_spend_usd",
               "avg_cpm_usd", "avg_order_value_usd", "panel_scale_factor",
               "status"], camp_rows)
    write_csv("fact_ad_exposures.csv",
              ["user_id", "campaign_id", "platform", "impressions", "clicks",
               "video_completions", "conversions", "first_exposure_date",
               "last_exposure_date"], exposures)
    write_csv("fact_campaign_daily.csv",
              ["activity_date", "campaign_id", "platform", "impressions", "clicks",
               "video_completions", "conversions", "spend_usd", "revenue_usd"],
              camp_daily)
    counts["dim_campaigns"] = len(camp_rows)
    counts["fact_ad_exposures"] = len(exposures)
    counts["fact_campaign_daily"] = len(camp_daily)

    rows = gen_connections(users, prof_by_user, top_interest)
    write_csv("fact_connections.csv",
              ["user_id", "connected_user_id", "platform", "connection_type",
               "interaction_strength", "same_university", "shared_top_interest"],
              rows)
    counts["fact_connections"] = len(rows)

    write_csv("dim_date.csv",
              ["date", "year", "month_num", "month_name", "week_of_year",
               "day_of_week_num", "day_name", "is_weekend", "academic_period"],
              gen_dim_date(dates))
    counts["dim_date"] = len(dates)

    dd = dictionary_rows()
    write_csv("data_dictionary.csv",
              ["table_name", "column_name", "data_type", "description",
               "collection_method", "sensitivity"], dd)
    counts["data_dictionary"] = len(dd)

    # ---- validation ----
    factor_by_camp = {r[0]: r[13] for r in camp_rows}
    expo_totals = {}
    for e in exposures:
        k = (e[1], e[2])
        expo_totals[k] = expo_totals.get(k, 0) + e[3] * factor_by_camp[e[1]]
    daily_totals = {}
    for r in camp_daily:
        k = (r[1], r[2])
        daily_totals[k] = daily_totals.get(k, 0) + r[3]
    assert expo_totals == daily_totals, "campaign daily rows must reconcile with exposures x scale factor"

    print("\nRow counts:")
    total_bytes = 0
    for name in sorted(os.listdir(OUT_DIR)):
        path = os.path.join(OUT_DIR, name)
        total_bytes += os.path.getsize(path)
    for k, v in sorted(counts.items()):
        print(f"  {k:28s} {v:>9,}")
    print(f"\nTotal rows: {sum(counts.values()):,}")
    print(f"Total size on disk: {total_bytes / 1e6:.1f} MB")
    print("Exposure/daily reconciliation check: PASSED")


if __name__ == "__main__":
    main()
