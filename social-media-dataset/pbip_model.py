#!/usr/bin/env python3
"""
Builds the CampusPulse semantic model (model.bim / TMSL JSON) for the PBIP.

Column data types are inferred from the actual CSVs, so the model always
matches the data that generate_data.py produced.
"""

import csv
import hashlib
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

# columns that must stay text even though they may look numeric
FORCE_TEXT = {
    "user_id", "connected_user_id", "profile_id", "device_id", "campaign_id",
    "segment_id", "interest_id", "mobile_advertising_id", "hashed_email",
    "phone", "handle", "email", "model", "primary_segment_id",
}

# numeric columns that must NOT be auto-summed in visuals
NO_SUMMARIZE = re.compile(
    r"(_id$|^age$|lat$|lon$|_score$|_pct$|_rate$|pct_|_usd$|strength|confidence"
    r"|^hour_of_day$|^year|_num$|^week_of_year$|_months$|factor$|openness"
    r"|conscientiousness|extraversion|agreeableness|neuroticism|count$"
    r"|^avg_|^total_|^member_count$|^panel_scale_factor$)"
)

GEO_CATEGORY = {
    "campus_lat": "Latitude", "campus_lon": "Longitude",
    "hometown_lat": "Latitude", "hometown_lon": "Longitude",
    "campus_city": "City", "hometown_city": "City",
    "campus_state": "StateOrProvince", "hometown_state": "StateOrProvince",
    "privacy_policy_url": "WebUrl",
}

SORT_BY = {
    "month_name": "month_num",
    "day_name": "day_of_week_num",
}

# Columns hidden from the report field list (PII kept in the model on purpose,
# so the privacy lesson can show it, but not surfaced for casual charting).
HIDDEN = {
    ("dim_users", "hashed_email"), ("dim_users", "phone"), ("dim_users", "email"),
    ("dim_devices", "mobile_advertising_id"),
}

INT_RE = re.compile(r"^-?\d+$")
DEC_RE = re.compile(r"^-?\d*\.\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def infer_types(path, sample=4000):
    """Return [(column_name, kind)] where kind is text/int/decimal/date/bool."""
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        header = next(rd)
        vals = [set() for _ in header]
        for i, row in enumerate(rd):
            if i >= sample:
                break
            for j, v in enumerate(row):
                if j < len(vals) and v != "" and len(vals[j]) < 60:
                    vals[j].add(v)
    kinds = []
    for name, vs in zip(header, vals):
        if name in FORCE_TEXT or not vs:
            kinds.append((name, "text"))
        elif vs <= {"TRUE", "FALSE"}:
            kinds.append((name, "bool"))
        elif all(DATE_RE.match(v) for v in vs):
            kinds.append((name, "date"))
        elif all(INT_RE.match(v) for v in vs):
            kinds.append((name, "int"))
        elif all(INT_RE.match(v) or DEC_RE.match(v) for v in vs):
            kinds.append((name, "decimal"))
        else:
            kinds.append((name, "text"))
    return kinds


TMSL_TYPE = {"text": "string", "int": "int64", "decimal": "double",
             "date": "dateTime", "bool": "boolean"}
M_TYPE = {"text": "type text", "int": "Int64.Type", "decimal": "type number",
          "date": "type date", "bool": "type logical"}


def m_partition(table, kinds):
    """Power Query expression for one CSV, as a list of lines."""
    transforms = ", ".join(f'{{"{n}", {M_TYPE[k]}}}' for n, k in kinds)
    return [
        "let",
        f'    Source = Csv.Document(DataFile("{table}.csv"), '
        f'[Delimiter=",", Columns={len(kinds)}, Encoding=65001, '
        'QuoteStyle=QuoteStyle.Csv]),',
        "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f'    Typed = Table.TransformColumnTypes(Headers, {{{transforms}}}, "en-US")',
        "in",
        "    Typed",
    ]


def build_column(table, name, kind):
    col = {
        "name": name,
        "dataType": TMSL_TYPE[kind],
        "sourceColumn": name,
        "summarizeBy": "none",
        "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}],
    }
    if kind in ("int", "decimal") and not NO_SUMMARIZE.search(name):
        col["summarizeBy"] = "sum"
    if kind == "decimal":
        col["formatString"] = "#,0.00"
    elif kind == "int":
        col["formatString"] = "#,0"
    elif kind == "date":
        col["formatString"] = "yyyy-mm-dd"
    if name in GEO_CATEGORY:
        col["dataCategory"] = GEO_CATEGORY[name]
    if name in SORT_BY:
        col["sortByColumn"] = SORT_BY[name]
    if (table, name) in HIDDEN:
        col["isHidden"] = True
    if table == "dim_date" and name == "date":
        col["isKey"] = True
    return col


# --------------------------------------------------------------- measures ---
# (table, name, DAX, formatString, displayFolder, description)
MEASURES = [
    # ---- engagement -------------------------------------------------------
    ("fact_engagement_daily", "Total Minutes",
     "SUM ( fact_engagement_daily[active_minutes] )", "#,0", "1 Volume",
     "Total minutes spent in social apps."),
    ("fact_engagement_daily", "Total Hours",
     "DIVIDE ( [Total Minutes], 60 )", "#,0", "1 Volume",
     "Total minutes expressed in hours."),
    ("fact_engagement_daily", "Active Students",
     "DISTINCTCOUNT ( fact_engagement_daily[user_id] )", "#,0", "1 Volume",
     "Distinct students with activity in the selected period."),
    ("fact_engagement_daily", "Active Days",
     "COUNTROWS ( fact_engagement_daily )", "#,0", "1 Volume",
     "User-platform-days recorded."),
    ("fact_engagement_daily", "Avg Minutes per Student per Day",
     "DIVIDE ( [Total Minutes], [Active Days] )", "#,0.0", "2 Rates",
     "Average minutes on one platform on one active day."),
    ("fact_engagement_daily", "Avg Daily Minutes per Student",
     "DIVIDE ( [Total Minutes], DISTINCTCOUNT ( fact_engagement_daily[activity_date] ) "
     "* [Active Students] )", "#,0.0", "2 Rates",
     "Average total minutes per student per calendar day, all platforms."),
    ("fact_engagement_daily", "Total Sessions",
     "SUM ( fact_engagement_daily[sessions] )", "#,0", "1 Volume",
     "App opens."),
    ("fact_engagement_daily", "Avg Session Length",
     "DIVIDE ( [Total Minutes], [Total Sessions] )", "#,0.0", "2 Rates",
     "Average minutes per app session."),
    ("fact_engagement_daily", "Posts Viewed",
     "SUM ( fact_engagement_daily[posts_viewed] )", "#,0", "1 Volume",
     "Pieces of content served."),
    ("fact_engagement_daily", "Videos Viewed",
     "SUM ( fact_engagement_daily[videos_viewed] )", "#,0", "3 Video",
     "Videos served."),
    ("fact_engagement_daily", "Video Completion %",
     "DIVIDE ( SUMX ( fact_engagement_daily, fact_engagement_daily[videos_viewed] "
     "* fact_engagement_daily[avg_video_completion_pct] ), [Videos Viewed] * 100 )",
     "0.0%", "3 Video",
     "Average share of each video watched, weighted by videos viewed."),
    ("fact_engagement_daily", "Videos Forwarded",
     "SUM ( fact_engagement_daily[videos_forwarded] )", "#,0", "3 Video",
     "Videos shared or forwarded to someone else."),
    ("fact_engagement_daily", "Forward Rate per 1K Videos",
     "DIVIDE ( [Videos Forwarded], [Videos Viewed] ) * 1000", "#,0.0", "3 Video",
     "Videos forwarded for every 1,000 videos watched."),
    ("fact_engagement_daily", "Forward Rate %",
     "DIVIDE ( [Videos Forwarded], [Videos Viewed] )", "0.00%", "3 Video",
     "Share of watched videos that get forwarded."),
    ("fact_engagement_daily", "Likes Given",
     "SUM ( fact_engagement_daily[likes_given] )", "#,0", "4 Interaction",
     "Likes and reactions given."),
    ("fact_engagement_daily", "Comments Written",
     "SUM ( fact_engagement_daily[comments_written] )", "#,0", "4 Interaction",
     "Comments posted."),
    ("fact_engagement_daily", "Posts Created",
     "SUM ( fact_engagement_daily[posts_created] )", "#,0", "4 Interaction",
     "Original posts published."),
    ("fact_engagement_daily", "Stories Viewed",
     "SUM ( fact_engagement_daily[stories_viewed] )", "#,0", "4 Interaction",
     "Stories viewed (zero on platforms without stories)."),
    ("fact_engagement_daily", "Interaction Rate %",
     "DIVIDE ( [Likes Given] + [Comments Written], [Posts Viewed] )", "0.0%",
     "4 Interaction", "Share of served content the student reacts to."),
    ("fact_engagement_daily", "Ads Seen",
     "SUM ( fact_engagement_daily[ads_seen] )", "#,0", "5 Advertising",
     "Ads served by all advertisers, not just CampusPulse campaigns."),
    ("fact_engagement_daily", "Ads Clicked",
     "SUM ( fact_engagement_daily[ads_clicked] )", "#,0", "5 Advertising",
     "Ads clicked."),
    ("fact_engagement_daily", "Ad CTR %",
     "DIVIDE ( [Ads Clicked], [Ads Seen] )", "0.00%", "5 Advertising",
     "Click-through rate across all ads served."),
    ("fact_engagement_daily", "Ads Seen per Day",
     "DIVIDE ( [Ads Seen], [Active Days] )", "#,0.0", "5 Advertising",
     "Ads served per student per active day."),
    ("fact_engagement_daily", "Late Night Minutes",
     "SUM ( fact_engagement_daily[late_night_minutes] )", "#,0", "6 Late night",
     "Minutes between 10 p.m. and 2 a.m."),
    ("fact_engagement_daily", "Late-Night Share %",
     "DIVIDE ( [Late Night Minutes], [Total Minutes] )", "0.0%", "6 Late night",
     "Share of all screen time that happens late at night."),

    # ---- hourly -----------------------------------------------------------
    ("fact_hourly_usage", "Avg Minutes in Hour",
     "SUM ( fact_hourly_usage[avg_minutes] )", "#,0.0", None,
     "Typical minutes online in the selected hour(s)."),
    ("fact_hourly_usage", "Avg Minutes per Student in Hour",
     "DIVIDE ( SUM ( fact_hourly_usage[avg_minutes] ), "
     "DISTINCTCOUNT ( fact_hourly_usage[user_id] ) )", "#,0.00", None,
     "Per-student minutes in the selected hour(s)."),

    # ---- campaigns --------------------------------------------------------
    ("fact_campaign_daily", "Total Impressions",
     "SUM ( fact_campaign_daily[impressions] )", "#,0", "1 Delivery",
     "Ad impressions delivered."),
    ("fact_campaign_daily", "Total Clicks",
     "SUM ( fact_campaign_daily[clicks] )", "#,0", "1 Delivery",
     "Ad clicks."),
    ("fact_campaign_daily", "Campaign Video Completions",
     "SUM ( fact_campaign_daily[video_completions] )", "#,0", "1 Delivery",
     "Campaign videos watched to the end."),
    ("fact_campaign_daily", "Total Conversions",
     "SUM ( fact_campaign_daily[conversions] )", "#,0", "1 Delivery",
     "Purchases or installs attributed to the campaign."),
    ("fact_campaign_daily", "Spend",
     "SUM ( fact_campaign_daily[spend_usd] )", "$#,0", "2 Money",
     "Media spend delivered."),
    ("fact_campaign_daily", "Revenue",
     "SUM ( fact_campaign_daily[revenue_usd] )", "$#,0", "2 Money",
     "Revenue attributed to the campaign."),
    ("fact_campaign_daily", "Profit",
     "[Revenue] - [Spend]", "$#,0", "2 Money",
     "Attributed revenue minus media spend."),
    ("fact_campaign_daily", "ROAS",
     "DIVIDE ( [Revenue], [Spend] )", "#,0.00", "2 Money",
     "Return on ad spend: revenue per dollar spent."),
    ("fact_campaign_daily", "CTR %",
     "DIVIDE ( [Total Clicks], [Total Impressions] )", "0.00%", "3 Efficiency",
     "Campaign click-through rate."),
    ("fact_campaign_daily", "CPM",
     "DIVIDE ( [Spend] * 1000, [Total Impressions] )", "$#,0.00", "3 Efficiency",
     "Cost per 1,000 impressions."),
    ("fact_campaign_daily", "CPC",
     "DIVIDE ( [Spend], [Total Clicks] )", "$#,0.00", "3 Efficiency",
     "Cost per click."),
    ("fact_campaign_daily", "CPA",
     "DIVIDE ( [Spend], [Total Conversions] )", "$#,0.00", "3 Efficiency",
     "Cost per acquisition."),
    ("fact_campaign_daily", "Conversion Rate %",
     "DIVIDE ( [Total Conversions], [Total Clicks] )", "0.0%", "3 Efficiency",
     "Share of clicks that convert."),
    ("fact_campaign_daily", "Campaign Video Completion Rate %",
     "DIVIDE ( [Campaign Video Completions], [Total Impressions] )", "0.0%",
     "3 Efficiency", "Share of impressions watched to the end."),
    ("fact_campaign_daily", "Budget",
     "SUM ( dim_campaigns[total_budget_usd] )", "$#,0", "2 Money",
     "Budget committed by the advertiser."),
    ("fact_campaign_daily", "Budget Used %",
     "DIVIDE ( [Spend], [Budget] )", "0.0%", "2 Money",
     "Share of committed budget actually delivered."),
    ("fact_campaign_daily", "Spend Running Total",
     "CALCULATE ( [Spend], FILTER ( ALLSELECTED ( dim_date[date] ), "
     "dim_date[date] <= MAX ( dim_date[date] ) ) )", "$#,0", "2 Money",
     "Cumulative spend across the selected period."),
    ("fact_campaign_daily", "Conversions Running Total",
     "CALCULATE ( [Total Conversions], FILTER ( ALLSELECTED ( dim_date[date] ), "
     "dim_date[date] <= MAX ( dim_date[date] ) ) )", "#,0", "1 Delivery",
     "Cumulative conversions across the selected period."),

    # ---- panel exposures --------------------------------------------------
    ("fact_ad_exposures", "Panel Reach",
     "DISTINCTCOUNT ( fact_ad_exposures[user_id] )", "#,0", None,
     "Panel members who saw the campaign at least once."),
    ("fact_ad_exposures", "Panel Impressions",
     "SUM ( fact_ad_exposures[impressions] )", "#,0", None,
     "Impressions measured on the research panel."),
    ("fact_ad_exposures", "Avg Frequency",
     "DIVIDE ( [Panel Impressions], [Panel Reach] )", "#,0.0", None,
     "Average times one person saw the campaign."),
    ("fact_ad_exposures", "Panel Converters",
     "CALCULATE ( DISTINCTCOUNT ( fact_ad_exposures[user_id] ), "
     "fact_ad_exposures[conversions] > 0 )", "#,0", None,
     "Panel members who converted."),
    ("fact_ad_exposures", "Panel Conversion Rate %",
     "DIVIDE ( [Panel Converters], [Panel Reach] )", "0.0%", None,
     "Share of reached panel members who converted."),
    ("fact_ad_exposures", "Reach %",
     "DIVIDE ( [Panel Reach], [Panel Size] )", "0.0%", None,
     "Share of the whole panel this campaign reached."),

    # ---- people -----------------------------------------------------------
    ("dim_users", "Panel Size",
     "DISTINCTCOUNT ( dim_users[user_id] )", "#,0", None,
     "Students in the research panel."),
    ("dim_users", "Avg Age",
     "AVERAGE ( dim_users[age] )", "#,0.0", None, "Average age."),
    ("dim_users", "Avg Discretionary Spend",
     "AVERAGE ( dim_users[est_monthly_discretionary_spend_usd] )", "$#,0", None,
     "Modeled monthly spending power."),
    ("dim_users", "Total Discretionary Spend",
     "SUM ( dim_users[est_monthly_discretionary_spend_usd] )", "$#,0", None,
     "Combined monthly spending power of the selection."),
    ("dim_users", "% With Part-Time Job",
     "DIVIDE ( CALCULATE ( COUNTROWS ( dim_users ), dim_users[has_part_time_job] "
     "= TRUE ), COUNTROWS ( dim_users ) )", "0.0%", None,
     "Share holding a part-time job."),
    ("dim_users", "Universities",
     "DISTINCTCOUNT ( dim_users[university] )", "#,0", None,
     "Campuses represented."),

    # ---- accounts ---------------------------------------------------------
    ("dim_platform_profiles", "Accounts",
     "COUNTROWS ( dim_platform_profiles )", "#,0", "1 Reach",
     "Social accounts held."),
    ("dim_platform_profiles", "Platforms per Student",
     "DIVIDE ( COUNTROWS ( dim_platform_profiles ), "
     "DISTINCTCOUNT ( dim_platform_profiles[user_id] ) )", "#,0.00", "1 Reach",
     "Average number of platforms each student is on."),
    ("dim_platform_profiles", "Adoption %",
     "DIVIDE ( DISTINCTCOUNT ( dim_platform_profiles[user_id] ), [Panel Size] )",
     "0.0%", "1 Reach", "Share of the panel with an account here."),
    ("dim_platform_profiles", "Total Followers",
     "SUM ( dim_platform_profiles[follower_count] )", "#,0", "1 Reach",
     "Combined follower count."),
    ("dim_platform_profiles", "Avg Followers",
     "AVERAGE ( dim_platform_profiles[follower_count] )", "#,0", "1 Reach",
     "Average followers per account."),
    ("dim_platform_profiles", "Median Followers",
     "MEDIAN ( dim_platform_profiles[follower_count] )", "#,0", "1 Reach",
     "Median followers - far below the average, because a few accounts are huge."),
    ("dim_platform_profiles", "Avg Posts per Week",
     "AVERAGE ( dim_platform_profiles[posts_per_week] )", "#,0.0", "1 Reach",
     "Average posting frequency."),
    ("dim_platform_profiles", "Avg Engagement Rate %",
     "DIVIDE ( AVERAGE ( dim_platform_profiles[engagement_rate_pct] ), 100 )",
     "0.00%", "1 Reach",
     "Engagements per follower per post - it falls as follower count rises."),
    ("dim_platform_profiles", "% Ads Personalization On",
     "DIVIDE ( CALCULATE ( COUNTROWS ( dim_platform_profiles ), "
     "dim_platform_profiles[ad_personalization_enabled] = TRUE ), "
     "COUNTROWS ( dim_platform_profiles ) )", "0.0%", "2 Privacy settings",
     "Accounts that left personalized advertising switched on."),
    ("dim_platform_profiles", "% Location Sharing On",
     "DIVIDE ( CALCULATE ( COUNTROWS ( dim_platform_profiles ), "
     "dim_platform_profiles[location_sharing_enabled] = TRUE ), "
     "COUNTROWS ( dim_platform_profiles ) )", "0.0%", "2 Privacy settings",
     "Accounts sharing precise location with the app."),
    ("dim_platform_profiles", "% Contacts Uploaded",
     "DIVIDE ( CALCULATE ( COUNTROWS ( dim_platform_profiles ), "
     "dim_platform_profiles[contacts_synced] = TRUE ), "
     "COUNTROWS ( dim_platform_profiles ) )", "0.0%", "2 Privacy settings",
     "Accounts that uploaded their phone contact list."),
    ("dim_platform_profiles", "% Private Accounts",
     "DIVIDE ( CALCULATE ( COUNTROWS ( dim_platform_profiles ), "
     "dim_platform_profiles[is_private_account] = TRUE ), "
     "COUNTROWS ( dim_platform_profiles ) )", "0.0%", "2 Privacy settings",
     "Accounts set to private."),
    ("dim_platform_profiles", "Micro-Influencers",
     "CALCULATE ( DISTINCTCOUNT ( dim_platform_profiles[user_id] ), "
     "dim_platform_profiles[follower_count] >= 8000 )", "#,0", "1 Reach",
     "Students with at least 8,000 followers somewhere."),

    # ---- devices ----------------------------------------------------------
    ("dim_devices", "Devices",
     "COUNTROWS ( dim_devices )", "#,0", None, "Devices in the selection."),
    ("dim_devices", "% Ad Tracking Allowed",
     "DIVIDE ( CALCULATE ( COUNTROWS ( dim_devices ), "
     "dim_devices[ad_tracking_allowed] = TRUE ), CALCULATE ( COUNTROWS "
     "( dim_devices ), dim_devices[device_type] = \"Smartphone\" ) )", "0.0%",
     None, "Phones allowing cross-app tracking (iOS asks, Android defaults on)."),
    ("dim_devices", "Avg Daily Pickups",
     "AVERAGE ( dim_devices[avg_daily_pickups] )", "#,0", None,
     "Times per day the phone is picked up."),
    ("dim_devices", "Avg % Time on WiFi",
     "DIVIDE ( AVERAGE ( dim_devices[pct_time_on_wifi] ), 100 )", "0%", None,
     "Share of usage on Wi-Fi rather than cellular."),

    # ---- segments ---------------------------------------------------------
    ("bridge_user_segments", "Segment Members",
     "DISTINCTCOUNT ( bridge_user_segments[user_id] )", "#,0", None,
     "Students in the selected segment(s)."),
    ("bridge_user_segments", "Avg Match Strength",
     "AVERAGE ( bridge_user_segments[match_strength] )", "#,0.0", None,
     "How strongly members fit the segment."),
    ("bridge_user_segments", "Segments per Student",
     "DIVIDE ( COUNTROWS ( bridge_user_segments ), "
     "DISTINCTCOUNT ( bridge_user_segments[user_id] ) )", "#,0.00", None,
     "Average number of sellable segments each student falls into."),
    ("dim_segments", "Segments",
     "COUNTROWS ( dim_segments )", "#,0", None, "Packaged audiences."),
    ("dim_segments", "Avg Suggested CPM",
     "AVERAGE ( dim_segments[suggested_cpm_usd] )", "$#,0.00", None,
     "Average rate card price per 1,000 impressions."),
    ("dim_segments", "Segment List Value",
     "SUMX ( dim_segments, dim_segments[member_count] * "
     "dim_segments[suggested_cpm_usd] )", "$#,0", None,
     "Rate-card value of the audience: members x CPM."),

    # ---- interests --------------------------------------------------------
    ("bridge_user_interests", "Students with Interest",
     "DISTINCTCOUNT ( bridge_user_interests[user_id] )", "#,0", None,
     "Students carrying the selected interest tag(s)."),
    ("bridge_user_interests", "Avg Affinity",
     "AVERAGE ( bridge_user_interests[affinity_score] )", "#,0.0", None,
     "Average strength of the interest signal."),
    ("bridge_user_interests", "Interest Tags",
     "COUNTROWS ( bridge_user_interests )", "#,0", None,
     "Interest tags applied."),
    ("bridge_user_interests", "Tags per Student",
     "DIVIDE ( COUNTROWS ( bridge_user_interests ), "
     "DISTINCTCOUNT ( bridge_user_interests[user_id] ) )", "#,0.0", None,
     "Interest tags held per student."),
    ("bridge_user_interests", "% Inferred Not Declared",
     "DIVIDE ( CALCULATE ( COUNTROWS ( bridge_user_interests ), "
     "bridge_user_interests[source] <> \"Declared\" ), "
     "COUNTROWS ( bridge_user_interests ) )", "0.0%", None,
     "Share of interest tags the student never actually told anyone."),

    # ---- network ----------------------------------------------------------
    ("fact_connections", "Friendships",
     "DIVIDE ( COUNTROWS ( fact_connections ), 2 )", "#,0", None,
     "Unique friendships (each edge is stored in both directions)."),
    ("fact_connections", "Connections",
     "COUNTROWS ( fact_connections )", "#,0", None,
     "Directed connection rows."),
    ("fact_connections", "Avg Connections per Student",
     "DIVIDE ( COUNTROWS ( fact_connections ), "
     "DISTINCTCOUNT ( fact_connections[user_id] ) )", "#,0.0", None,
     "Average network size."),
    ("fact_connections", "% Same University",
     "DIVIDE ( CALCULATE ( COUNTROWS ( fact_connections ), "
     "fact_connections[same_university] = TRUE ), COUNTROWS ( fact_connections ) )",
     "0.0%", None, "Share of friendships that are same-campus (homophily)."),
    ("fact_connections", "Avg Interaction Strength",
     "AVERAGE ( fact_connections[interaction_strength] )", "#,0.000", None,
     "How often connected students actually interact."),

    # ---- psychographics ---------------------------------------------------
    ("dim_psychographics", "Avg Impulse Buying Score",
     "AVERAGE ( dim_psychographics[impulse_buying_score] )", "#,0.0", None,
     "Modeled tendency to buy on impulse."),
    ("dim_psychographics", "Avg Social Influence Score",
     "AVERAGE ( dim_psychographics[social_influence_score] )", "#,0.0", None,
     "Modeled sway over the student's own network."),
    ("dim_psychographics", "Avg Attention Span Score",
     "AVERAGE ( dim_psychographics[attention_span_score] )", "#,0.0", None,
     "Modeled attention span."),
    ("dim_psychographics", "Avg Openness",
     "AVERAGE ( dim_psychographics[openness] )", "#,0.0", "Big Five",
     "Big Five openness."),
    ("dim_psychographics", "Avg Conscientiousness",
     "AVERAGE ( dim_psychographics[conscientiousness] )", "#,0.0", "Big Five",
     "Big Five conscientiousness."),
    ("dim_psychographics", "Avg Extraversion",
     "AVERAGE ( dim_psychographics[extraversion] )", "#,0.0", "Big Five",
     "Big Five extraversion."),
    ("dim_psychographics", "Avg Agreeableness",
     "AVERAGE ( dim_psychographics[agreeableness] )", "#,0.0", "Big Five",
     "Big Five agreeableness."),
    ("dim_psychographics", "Avg Neuroticism",
     "AVERAGE ( dim_psychographics[neuroticism] )", "#,0.0", "Big Five",
     "Big Five neuroticism."),
    ("dim_psychographics", "% Political Lean Inferred",
     "DIVIDE ( CALCULATE ( COUNTROWS ( dim_psychographics ), "
     "dim_psychographics[inferred_political_lean] <> \"Not inferred\" ), "
     "COUNTROWS ( dim_psychographics ) )", "0.0%", None,
     "Share of students given a political label they never volunteered."),
    ("dim_psychographics", "Avg Political Lean Confidence",
     "CALCULATE ( AVERAGE ( dim_psychographics[political_lean_confidence] ), "
     "dim_psychographics[inferred_political_lean] <> \"Not inferred\" )",
     "0.00", None, "Model confidence where a political label was assigned."),
    ("dim_psychographics", "In-Market Students",
     "CALCULATE ( COUNTROWS ( dim_psychographics ), "
     "FILTER ( dim_psychographics, dim_psychographics[intent_new_phone] = TRUE "
     "|| dim_psychographics[intent_travel_6mo] = TRUE "
     "|| dim_psychographics[intent_meal_delivery] = TRUE "
     "|| dim_psychographics[intent_gym_membership] = TRUE "
     "|| dim_psychographics[intent_credit_card] = TRUE ) )", "#,0", None,
     "Students flagged as in-market for at least one product category."),

    # ---- the privacy lens -------------------------------------------------
    ("data_dictionary", "Columns Tracked",
     "COUNTROWS ( data_dictionary )", "#,0", None,
     "Data points held on every student."),
    ("data_dictionary", "Declared Columns",
     "CALCULATE ( COUNTROWS ( data_dictionary ), "
     "data_dictionary[collection_method] = \"Declared by user\" )", "#,0", None,
     "Columns the user actually typed in themselves."),
    ("data_dictionary", "Inferred Columns",
     "CALCULATE ( COUNTROWS ( data_dictionary ), "
     "data_dictionary[collection_method] = \"Inferred by model\" )", "#,0", None,
     "Columns produced by a model, never volunteered."),
    ("data_dictionary", "Observed Columns",
     "CALCULATE ( COUNTROWS ( data_dictionary ), "
     "data_dictionary[collection_method] = \"Observed behavior\" )", "#,0", None,
     "Columns recorded by watching behavior."),
    ("data_dictionary", "% Declared",
     "DIVIDE ( [Declared Columns], [Columns Tracked] )", "0.0%", None,
     "Share of everything held that the student knowingly provided."),
    ("data_dictionary", "% Inferred",
     "DIVIDE ( [Inferred Columns], [Columns Tracked] )", "0.0%", None,
     "Share of everything held that was guessed by a model."),
    ("data_dictionary", "High Sensitivity Columns",
     "CALCULATE ( COUNTROWS ( data_dictionary ), "
     "data_dictionary[sensitivity] = \"High\" )", "#,0", None,
     "Columns tagged high sensitivity."),
    ("data_dictionary", "% High Sensitivity",
     "DIVIDE ( [High Sensitivity Columns], [Columns Tracked] )", "0.0%", None,
     "Share of columns tagged high sensitivity."),
]


# ---------------------------------------------------------- relationships ---
# (fromTable, fromColumn, toTable, toColumn, both_directions, one_to_one)
RELATIONSHIPS = [
    ("fact_engagement_daily", "user_id", "dim_users", "user_id", False, False),
    ("fact_engagement_daily", "platform", "dim_platforms", "platform", False, False),
    ("fact_engagement_daily", "activity_date", "dim_date", "date", False, False),
    ("fact_hourly_usage", "user_id", "dim_users", "user_id", False, False),
    ("fact_ad_exposures", "user_id", "dim_users", "user_id", False, False),
    ("fact_ad_exposures", "campaign_id", "dim_campaigns", "campaign_id", False, False),
    ("fact_ad_exposures", "platform", "dim_platforms", "platform", False, False),
    ("fact_campaign_daily", "campaign_id", "dim_campaigns", "campaign_id", False, False),
    ("fact_campaign_daily", "platform", "dim_platforms", "platform", False, False),
    ("fact_campaign_daily", "activity_date", "dim_date", "date", False, False),
    ("fact_connections", "user_id", "dim_users", "user_id", False, False),
    ("fact_connections", "platform", "dim_platforms", "platform", False, False),
    ("dim_platform_profiles", "user_id", "dim_users", "user_id", False, False),
    ("dim_platform_profiles", "platform", "dim_platforms", "platform", False, False),
    # 1:1 - lets chronotype / values segment / intent flags slice everything
    ("dim_psychographics", "user_id", "dim_users", "user_id", True, True),
    # bidirectional so device brand and tracking opt-in can slice the facts
    ("dim_devices", "user_id", "dim_users", "user_id", True, False),
    # bridges must be bidirectional so a chosen segment/interest filters users
    ("bridge_user_segments", "user_id", "dim_users", "user_id", True, False),
    ("bridge_user_segments", "segment_id", "dim_segments", "segment_id", False, False),
    ("bridge_user_interests", "user_id", "dim_users", "user_id", True, False),
    ("bridge_user_interests", "interest_id", "dim_interests", "interest_id", False, False),
    # Deliberately NOT related: dim_campaigns[primary_segment_id] -> dim_segments.
    # Because bridge_user_segments filters dim_users in both directions, adding
    # it would give dim_segments two active filter paths into fact_ad_exposures
    # (via dim_campaigns, and via the bridge through dim_users), which Power BI
    # rejects as an ambiguous path. primary_segment_id stays a lookup column.
]


def build_model(default_folder=r"C:\CampusPulse\data"):
    tables = []
    table_names = sorted(f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv"))

    measures_by_table = {}
    for tbl, name, dax, fmt, folder, desc in MEASURES:
        measures_by_table.setdefault(tbl, []).append((name, dax, fmt, folder, desc))

    for t in table_names:
        kinds = infer_types(os.path.join(DATA_DIR, f"{t}.csv"))
        table = {
            "name": t,
            "columns": [build_column(t, n, k) for n, k in kinds],
            "partitions": [{
                "name": t,
                "mode": "import",
                "source": {"type": "m", "expression": m_partition(t, kinds)},
            }],
            "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
        }
        if t == "dim_date":
            table["dataCategory"] = "Time"
        if t in measures_by_table:
            table["measures"] = []
            for name, dax, fmt, folder, desc in measures_by_table[t]:
                m = {"name": name, "expression": dax, "formatString": fmt,
                     "description": desc}
                if folder:
                    m["displayFolder"] = folder
                table["measures"].append(m)
        tables.append(table)

    relationships = []
    for ft, fc, tt, tc, both, one2one in RELATIONSHIPS:
        # deterministic GUID so rebuilds keep stable relationship identities
        h = hashlib.md5(f"{ft}|{fc}|{tt}|{tc}".encode()).hexdigest()
        r = {
            "name": f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}",
            "fromTable": ft, "fromColumn": fc,
            "toTable": tt, "toColumn": tc,
        }
        if one2one:
            r["fromCardinality"] = "one"
            r["toCardinality"] = "one"
        if both:
            r["crossFilteringBehavior"] = "bothDirections"
        relationships.append(r)

    # In Power Query M a backslash is an ordinary character; only a double
    # quote needs escaping, by doubling it.
    folder_literal = default_folder.replace('"', '""')
    expressions = [
        {
            "name": "DataFolder",
            "kind": "m",
            "expression": [
                f'"{folder_literal}" meta [IsParameterQuery=true, Type="Text", '
                'IsParameterQueryRequired=true]',
            ],
            "description": "Folder holding the CampusPulse CSV files. "
                           "Set this once, then refresh.",
            "annotations": [{"name": "PBI_ResultType", "value": "Text"}],
        },
        {
            "name": "DataFile",
            "kind": "m",
            "expression": [
                "let",
                "    Fn = (fileName as text) as binary =>",
                "        let",
                "            Sep = if Text.EndsWith(DataFolder, \"\\\") or "
                "Text.EndsWith(DataFolder, \"/\") then \"\" else \"\\\",",
                "            Path = DataFolder & Sep & fileName",
                "        in",
                "            File.Contents(Path)",
                "in",
                "    Fn",
            ],
            "description": "Reads one CSV from DataFolder, with or without a "
                           "trailing slash.",
            "annotations": [{"name": "PBI_ResultType", "value": "Function"}],
        },
    ]

    return {
        "name": "CampusPulse",
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "relationships": relationships,
            "expressions": expressions,
            "annotations": [
                {"name": "PBI_QueryOrder",
                 "value": '["' + '","'.join(["DataFolder", "DataFile"] + table_names) + '"]'},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }
