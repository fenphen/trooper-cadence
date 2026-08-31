#!/usr/bin/env python3
"""
Page and visual specification for the CampusPulse Power BI report.

Declared independently of the on-disk JSON format: each visual is
(kind, roles, options) and a small layout engine assigns pixel positions.
pbip_report.py renders these into PBIR visual.json files.

Field shorthand:
    "Table[column]"   -> a column projection
    "[Measure Name]"  -> a measure projection
"""

CANVAS_W = 1280
CANVAS_H = 720
PAD = 10


class Page:
    def __init__(self, name, display, subtitle, accent):
        self.name = name
        self.display = display
        self.subtitle = subtitle
        self.accent = accent
        self.visuals = []
        self._y = PAD

    def row(self, height, items, gap=PAD, y=None):
        """items = [(weight, kind, roles, opts), ...] laid out left to right."""
        top = self._y if y is None else y
        total_w = CANVAS_W - 2 * PAD - gap * (len(items) - 1)
        weights = sum(i[0] for i in items)
        x = PAD
        for idx, (w, kind, roles, opts) in enumerate(items):
            width = int(total_w * w / weights)
            if idx == len(items) - 1:
                width = CANVAS_W - PAD - x
            self.visuals.append(dict(kind=kind, roles=roles, opts=opts or {},
                                     x=x, y=top, w=width, h=height))
            x += width + gap
        if y is None:
            self._y = top + height + gap
        return self

    def banner(self):
        self.visuals.append(dict(
            kind="textbox", roles={}, x=PAD, y=PAD, w=CANVAS_W - 2 * PAD, h=52,
            opts={"heading": self.display, "sub": self.subtitle,
                  "accent": self.accent}))
        self._y = PAD + 52 + PAD
        return self


def build_pages():
    pages = []

    # ================================================== 1. AUDIENCE 360 =====
    p = Page("audience360", "Audience 360",
             "Who the 2,000 students in the CampusPulse panel are - and how much "
             "of this they never told anyone.", "#2E6BE6")
    p.banner()
    p.row(48, [
        (1, "slicer", {"Values": ["dim_users[university]"]},
         {"mode": "Dropdown", "title": "University"}),
        (1, "slicer", {"Values": ["dim_users[class_year]"]},
         {"mode": "Dropdown", "title": "Class year"}),
        (1, "slicer", {"Values": ["dim_segments[segment_name]"]},
         {"mode": "Dropdown", "title": "Audience segment"}),
        (1, "slicer", {"Values": ["dim_psychographics[chronotype]"]},
         {"mode": "Dropdown", "title": "Chronotype"}),
        (1, "slicer", {"Values": ["dim_platforms[platform]"]},
         {"mode": "Dropdown", "title": "Platform"}),
    ])
    p.row(82, [
        (1, "card", {"Values": ["[Panel Size]"]}, {"title": "Students"}),
        (1, "card", {"Values": ["[Universities]"]}, {"title": "Campuses"}),
        (1, "card", {"Values": ["[Platforms per Student]"]},
         {"title": "Platforms each"}),
        (1, "card", {"Values": ["[Avg Age]"]}, {"title": "Average age"}),
        (1, "card", {"Values": ["[Avg Discretionary Spend]"]},
         {"title": "Monthly spend power"}),
        (1, "card", {"Values": ["[% With Part-Time Job]"]},
         {"title": "Has a job"}),
    ])
    p.row(250, [
        (34, "map", {"Category": ["dim_users[campus_city]"],
                     "Size": ["[Panel Size]"]},
         {"title": "Where the panel goes to school"}),
        (22, "clusteredColumnChart", {"Category": ["dim_users[class_year]"],
                                      "Y": ["[Panel Size]"]},
         {"title": "Students by class year"}),
        (22, "donutChart", {"Category": ["dim_users[gender]"],
                            "Y": ["[Panel Size]"]},
         {"title": "Gender"}),
        (22, "barChart", {"Category": ["dim_users[housing_type]"],
                          "Y": ["[Panel Size]"]},
         {"title": "Housing (inferred from location patterns)"}),
    ])
    p.row(236, [
        (1, "barChart", {"Category": ["dim_users[major]"],
                         "Y": ["[Panel Size]"]},
         {"title": "Majors (inferred from bio text and page follows)"}),
        (1, "clusteredColumnChart", {"Category": ["dim_platforms[platform]"],
                                     "Y": ["[Adoption %]"]},
         {"title": "Platform adoption across the panel"}),
        (1, "narrative", {}, {"title": "What the data says"}),
    ])
    pages.append(p)

    # ============================================ 2. SCREEN TIME & BEHAVIOR ==
    p = Page("screentime", "Screen Time & Behavior",
             "Every minute, every video, every scroll - measured per student, "
             "per platform, per hour of the day.", "#8B2FD6")
    p.banner()
    p.row(48, [
        (1, "slicer", {"Values": ["dim_platforms[platform]"]},
         {"mode": "Dropdown", "title": "Platform"}),
        (1, "slicer", {"Values": ["dim_date[academic_period]"]},
         {"mode": "Dropdown", "title": "Academic period"}),
        (1, "slicer", {"Values": ["dim_psychographics[chronotype]"]},
         {"mode": "Dropdown", "title": "Chronotype"}),
        (1, "slicer", {"Values": ["dim_users[class_year]"]},
         {"mode": "Dropdown", "title": "Class year"}),
        (1, "slicer", {"Values": ["dim_date[date]"]},
         {"mode": "Between", "title": "Date range"}),
    ])
    p.row(82, [
        (1, "card", {"Values": ["[Total Hours]"]}, {"title": "Hours watched"}),
        (1, "card", {"Values": ["[Avg Daily Minutes per Student]"]},
         {"title": "Minutes / student / day"}),
        (1, "card", {"Values": ["[Avg Session Length]"]},
         {"title": "Minutes per session"}),
        (1, "card", {"Values": ["[Video Completion %]"]},
         {"title": "Video completion"}),
        (1, "card", {"Values": ["[Forward Rate per 1K Videos]"]},
         {"title": "Forwards / 1K videos"}),
        (1, "card", {"Values": ["[Late-Night Share %]"]},
         {"title": "Late-night share"}),
    ])
    p.row(240, [
        (60, "lineChart", {"Category": ["dim_date[date]"],
                           "Series": ["dim_platforms[platform]"],
                           "Y": ["[Total Minutes]"]},
         {"title": "Daily minutes by platform (watch the fall semester start "
                   "on Aug 24)"}),
        (40, "lineChart", {"Category": ["fact_hourly_usage[hour_of_day]"],
                           "Series": ["fact_hourly_usage[day_type]"],
                           "Y": ["[Avg Minutes in Hour]"]},
         {"title": "When they are online, hour by hour"}),
    ])
    p.row(246, [
        (25, "barChart", {"Category": ["dim_platforms[platform]"],
                          "Y": ["[Video Completion %]"]},
         {"title": "Video completion by platform"}),
        (25, "barChart", {"Category": ["dim_platforms[platform]"],
                          "Y": ["[Forward Rate per 1K Videos]"]},
         {"title": "Forwarding by platform"}),
        (25, "clusteredColumnChart",
         {"Category": ["dim_psychographics[chronotype]"],
          "Y": ["[Late-Night Share %]"]},
         {"title": "Late-night share by chronotype"}),
        (25, "narrative", {}, {"title": "What the data says"}),
    ])
    pages.append(p)

    # ============================================ 3. SEGMENT MARKETPLACE ====
    p = Page("segments", "Segment Marketplace",
             "The product catalogue: twelve packaged audiences, priced per "
             "thousand impressions and ready to sell.", "#0E8C6A")
    p.banner()
    p.row(48, [
        (1, "slicer", {"Values": ["dim_segments[segment_name]"]},
         {"mode": "Dropdown", "title": "Segment"}),
        (1, "slicer", {"Values": ["dim_interests[interest_category]"]},
         {"mode": "Dropdown", "title": "Interest category"}),
        (1, "slicer", {"Values": ["bridge_user_interests[source]"]},
         {"mode": "Dropdown", "title": "How the interest was learned"}),
        (1, "slicer", {"Values": ["dim_users[university]"]},
         {"mode": "Dropdown", "title": "University"}),
        (1, "slicer", {"Values": ["dim_psychographics[values_segment]"]},
         {"mode": "Dropdown", "title": "Values archetype"}),
    ])
    p.row(82, [
        (1, "card", {"Values": ["[Segments]"]}, {"title": "Segments sold"}),
        (1, "card", {"Values": ["[Segment Members]"]}, {"title": "Members"}),
        (1, "card", {"Values": ["[Segments per Student]"]},
         {"title": "Segments per student"}),
        (1, "card", {"Values": ["[Avg Match Strength]"]},
         {"title": "Avg match strength"}),
        (1, "card", {"Values": ["[Avg Suggested CPM]"]}, {"title": "Avg CPM"}),
        (1, "card", {"Values": ["[Segment List Value]"]},
         {"title": "Rate-card value"}),
    ])
    p.row(258, [
        (58, "tableEx", {"Values": ["dim_segments[segment_name]",
                                    "dim_segments[tagline]",
                                    "dim_segments[member_count]",
                                    "dim_segments[avg_match_strength]",
                                    "dim_segments[top_platform]",
                                    "dim_segments[suggested_cpm_usd]"]},
         {"title": "The rate card"}),
        (42, "scatterChart", {"Category": ["dim_segments[segment_name]"],
                              "X": ["[Segment Members]"],
                              "Y": ["[Avg Suggested CPM]"],
                              "Size": ["[Segment List Value]"]},
         {"title": "Reach vs price - the bigger the bubble, the more it is worth"}),
    ])
    p.row(228, [
        (28, "barChart", {"Category": ["dim_segments[segment_name]"],
                          "Y": ["[Segment Members]"]},
         {"title": "Members per segment"}),
        (28, "treemap", {"Group": ["dim_interests[interest_category]"],
                         "Values": ["[Interest Tags]"]},
         {"title": "Interest taxonomy"}),
        (22, "clusteredColumnChart",
         {"Category": ["bridge_user_interests[source]"],
          "Y": ["[Interest Tags]"]},
         {"title": "Declared vs guessed"}),
        (22, "narrative", {}, {"title": "What the data says"}),
    ])
    pages.append(p)

    # ============================================ 4. CAMPAIGN PERFORMANCE ===
    p = Page("campaigns", "Campaign Performance",
             "What the advertisers got for their money - delivery, efficiency "
             "and return across twelve campaigns.", "#D6600F")
    p.banner()
    p.row(48, [
        (1, "slicer", {"Values": ["dim_campaigns[campaign_name]"]},
         {"mode": "Dropdown", "title": "Campaign"}),
        (1, "slicer", {"Values": ["dim_campaigns[objective]"]},
         {"mode": "Dropdown", "title": "Objective"}),
        (1, "slicer", {"Values": ["dim_campaigns[advertiser_vertical]"]},
         {"mode": "Dropdown", "title": "Vertical"}),
        (1, "slicer", {"Values": ["dim_platforms[platform]"]},
         {"mode": "Dropdown", "title": "Platform"}),
        (1, "slicer", {"Values": ["dim_date[date]"]},
         {"mode": "Between", "title": "Flight dates"}),
    ])
    p.row(82, [
        (1, "card", {"Values": ["[Spend]"]}, {"title": "Spend"}),
        (1, "card", {"Values": ["[Total Impressions]"]}, {"title": "Impressions"}),
        (1, "card", {"Values": ["[CTR %]"]}, {"title": "CTR"}),
        (1, "card", {"Values": ["[CPM]"]}, {"title": "CPM"}),
        (1, "card", {"Values": ["[Total Conversions]"]}, {"title": "Conversions"}),
        (1, "card", {"Values": ["[CPA]"]}, {"title": "Cost per acquisition"}),
        (1, "card", {"Values": ["[ROAS]"]}, {"title": "ROAS"}),
        (1, "card", {"Values": ["[Reach %]"]}, {"title": "Panel reach"}),
    ])
    p.row(236, [
        (55, "lineClusteredColumnComboChart",
         {"Category": ["dim_date[date]"],
          "Y": ["[Spend]"],
          "Y2": ["[Total Conversions]"]},
         {"title": "Daily spend and conversions"}),
        (45, "barChart", {"Category": ["dim_campaigns[campaign_name]"],
                          "Y": ["[ROAS]"]},
         {"title": "Return on ad spend by campaign"}),
    ])
    p.row(248, [
        (26, "clusteredColumnChart", {"Category": ["dim_platforms[platform]"],
                                      "Y": ["[CTR %]"]},
         {"title": "CTR by platform"}),
        (26, "funnel", {"Category": ["dim_campaigns[objective]"],
                        "Y": ["[Total Impressions]"]},
         {"title": "Impressions by objective"}),
        (26, "decompositionTree",
         {"Analyze": ["[Total Conversions]"],
          "ExplainBy": ["dim_campaigns[campaign_name]",
                        "dim_platforms[platform]",
                        "dim_campaigns[objective]",
                        "dim_campaigns[advertiser_vertical]"]},
         {"title": "Break conversions down"}),
        (22, "narrative", {}, {"title": "What the data says"}),
    ])
    pages.append(p)

    # ============================================ 5. NETWORK & INFLUENCE ====
    p = Page("network", "Network & Influence",
             "The social graph: who knows whom, and which students carry the "
             "most weight with their friends.", "#B5197A")
    p.banner()
    p.row(48, [
        (1, "slicer", {"Values": ["dim_users[university]"]},
         {"mode": "Dropdown", "title": "University"}),
        (1, "slicer", {"Values": ["dim_platforms[platform]"]},
         {"mode": "Dropdown", "title": "Platform"}),
        (1, "slicer", {"Values": ["dim_psychographics[content_creator_level]"]},
         {"mode": "Dropdown", "title": "Creator level"}),
        (1, "slicer", {"Values": ["fact_connections[connection_type]"]},
         {"mode": "Dropdown", "title": "Connection type"}),
        (1, "slicer", {"Values": ["dim_users[class_year]"]},
         {"mode": "Dropdown", "title": "Class year"}),
    ])
    p.row(82, [
        (1, "card", {"Values": ["[Friendships]"]}, {"title": "Friendships"}),
        (1, "card", {"Values": ["[Avg Connections per Student]"]},
         {"title": "Avg network size"}),
        (1, "card", {"Values": ["[% Same University]"]},
         {"title": "Same-campus friendships"}),
        (1, "card", {"Values": ["[Avg Interaction Strength]"]},
         {"title": "Avg interaction strength"}),
        (1, "card", {"Values": ["[Micro-Influencers]"]},
         {"title": "Micro-influencers (8k+)"}),
        (1, "card", {"Values": ["[Median Followers]"]},
         {"title": "Median followers"}),
    ])
    p.row(242, [
        (52, "scatterChart", {"Category": ["dim_platform_profiles[handle]"],
                              "X": ["[Avg Followers]"],
                              "Y": ["[Avg Engagement Rate %]"],
                              "Size": ["[Avg Posts per Week]"]},
         {"title": "Followers vs engagement rate - the bigger the audience, "
                   "the colder it gets"}),
        (48, "tableEx", {"Values": ["dim_platform_profiles[handle]",
                                    "dim_platform_profiles[platform]",
                                    "dim_platform_profiles[follower_count]",
                                    "dim_platform_profiles[engagement_rate_pct]",
                                    "dim_platform_profiles[posts_per_week]"]},
         {"title": "Buy these students once and they sell all semester"}),
    ])
    p.row(242, [
        (26, "clusteredColumnChart", {"Category": ["dim_platforms[platform]"],
                                      "Y": ["[Connections]"]},
         {"title": "Connections by platform"}),
        (26, "barChart",
         {"Category": ["dim_psychographics[content_creator_level]"],
          "Y": ["[Panel Size]"]},
         {"title": "Creators vs lurkers"}),
        (26, "keyDrivers",
         {"Target": ["dim_psychographics[content_creator_level]"],
          "ExplainBy": ["dim_users[class_year]", "dim_users[housing_type]",
                        "dim_psychographics[chronotype]",
                        "dim_psychographics[values_segment]"]},
         {"title": "What predicts a creator"}),
        (22, "narrative", {}, {"title": "What the data says"}),
    ])
    pages.append(p)

    # ================================================ 6. THE PRIVACY LENS ===
    p = Page("privacy", "The Privacy Lens",
             "165 columns are held on every student. Thirteen of them were "
             "actually volunteered.", "#B3261E")
    p.banner()
    p.row(48, [
        (1, "slicer", {"Values": ["data_dictionary[table_name]"]},
         {"mode": "Dropdown", "title": "Table"}),
        (1, "slicer", {"Values": ["data_dictionary[collection_method]"]},
         {"mode": "Dropdown", "title": "How it was collected"}),
        (1, "slicer", {"Values": ["data_dictionary[sensitivity]"]},
         {"mode": "Dropdown", "title": "Sensitivity"}),
        (1, "slicer", {"Values": ["dim_devices[operating_system]"]},
         {"mode": "Dropdown", "title": "Operating system"}),
        (1, "slicer", {"Values": ["dim_platforms[platform]"]},
         {"mode": "Dropdown", "title": "Platform"}),
    ])
    p.row(82, [
        (1, "card", {"Values": ["[Columns Tracked]"]},
         {"title": "Data points held"}),
        (1, "card", {"Values": ["[% Declared]"]},
         {"title": "Actually volunteered"}),
        (1, "card", {"Values": ["[% Inferred]"]},
         {"title": "Guessed by a model"}),
        (1, "card", {"Values": ["[% High Sensitivity]"]},
         {"title": "High sensitivity"}),
        (1, "card", {"Values": ["[% Political Lean Inferred]"]},
         {"title": "Given a political label"}),
        (1, "card", {"Values": ["[% Ad Tracking Allowed]"]},
         {"title": "Phones allowing tracking"}),
    ])
    p.row(238, [
        (30, "barChart", {"Category": ["data_dictionary[collection_method]"],
                          "Y": ["[Columns Tracked]"]},
         {"title": "Where the data actually comes from"}),
        (40, "pivotTable", {"Rows": ["data_dictionary[table_name]"],
                            "Columns": ["data_dictionary[sensitivity]"],
                            "Values": ["[Columns Tracked]"]},
         {"title": "Sensitivity by table"}),
        (30, "clusteredColumnChart",
         {"Category": ["dim_platforms[platform]"],
          "Y": ["[% Ads Personalization On]", "[% Location Sharing On]",
                "[% Contacts Uploaded]"]},
         {"title": "Privacy settings students left switched on"}),
    ])
    p.row(246, [
        (26, "clusteredColumnChart",
         {"Category": ["dim_psychographics[inferred_political_lean]"],
          "Y": ["[Panel Size]"]},
         {"title": "A label nobody asked for"}),
        (26, "donutChart", {"Category": ["data_dictionary[sensitivity]"],
                            "Y": ["[Columns Tracked]"]},
         {"title": "Sensitivity mix"}),
        (26, "tableEx", {"Values": ["data_dictionary[table_name]",
                                    "data_dictionary[column_name]",
                                    "data_dictionary[description]"]},
         {"title": "Every field held on a student"}),
        (22, "narrative", {}, {"title": "What the data says"}),
    ])
    pages.append(p)

    return pages
