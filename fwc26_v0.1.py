#---------------------------------------------------------------------------------------------------------------------------------
### Authenticator
#---------------------------------------------------------------------------------------------------------------------------------
import streamlit as st
#---------------------------------------------------------------------------------------------------------------------------------
### Import Libraries
#---------------------------------------------------------------------------------------------------------------------------------
import re
import requests
#----------------------------------------
import numpy as np
import pandas as pd
#----------------------------------------
import sys, os
from io import BytesIO, StringIO
from datetime import datetime, timedelta
#----------------------------------------
import pytz
from pytz import timezone
#----------------------------------------
import snowflake.connector
#---------------------------------------------------------------------------------------------------------------------------------
# Page Configuration
#---------------------------------------------------------------------------------------------------------------------------------
st.set_page_config(page_title="Fifa World Cup | 2026",
layout="wide",
page_icon="⚽",
initial_sidebar_state="auto")
#---------------------------------------------------------------------------------------------------------------------------------
# Custom CSS Styles
#---------------------------------------------------------------------------------------------------------------------------------
st.markdown("""
<style>
footer {visibility: hidden;}
/* Hide Streamlit's default header and menu */
footer {visibility: hidden;}
header {visibility: hidden;}
/* Remove default padding from main container */
.block-container {
padding-top: 0.5rem !important;
padding-bottom: 0rem !important;
}
/* Remove margin from first elements */
.element-container:first-of-type {
margin-top: 0 !important;
}
</style>
""", unsafe_allow_html=True)
#---------------------------------------------------------------------------------------------------------------------------------
### Description for your Streamlit app
#---------------------------------------------------------------------------------------------------------------------------------
st.markdown(
"""
<style>
.title-large {
text-align: center;
font-size: 35px;
font-weight: bold;
background: linear-gradient(120deg, #0056b3, #0d4a96);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
}
.title-small {
text-align: center;
font-size: 20px;
background: linear-gradient(to left, red, orange, blue, indigo, violet);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
}
.version-badge {
text-align: center;
display: inline-block;
background: linear-gradient(120deg, #0056b3, #0d4a96);
color: white;
padding: 2px 12px;
border-radius: 20px;
font-size: 1.15rem;
margin-top: 8px;
font-weight: 600;
letter-spacing: 0.5px;
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
</style>
<div style="text-align: center;">
<div class="title-large">⚽ FIFA World Cup 2026</div>
</div>
""",unsafe_allow_html=True)

st.markdown(
"""
<style>
.footer {
position: fixed; left: 0; bottom: 0;width: 100%;background-color: #F0F2F6;text-align: center;padding: 10px;font-size: 14px;
color: #333;z-index: 100;}
.footer p {margin: 0;}
.footer .highlight {font-weight: bold;color: blue;}
</style>
<div class="footer">
<p>© 2026 | Created by : <span class="highlight">Avijit Chakraborty</span> <a href="mailto:avijit.mba18@gmail.com"> 📩 </a> | <span class="highlight">Thank you for visiting the app | Unauthorized uses or copying is strictly prohibited | For best view of the app, please zoom out the browser to 75%.</span> </p>
</div>
""",unsafe_allow_html=True)

#---------------------------------------------------------------------------------------------------------------------------------
### Connections
#---------------------------------------------------------------------------------------------------------------------------------
ESPN_API = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
#---------------------------------------------------------------------------------------------------------------------------------
### Functions & Definitions
#---------------------------------------------------------------------------------------------------------------------------------
@st.cache_data(ttl=120)
def run_query(query):
    conn = snowflake.connector.connect(
        account=st.secrets["snowflake"]["account"],
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema=st.secrets["snowflake"]["schema"],
    )
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()

def _get_date_range():
    """Return a 3-day date range (yesterday-tomorrow ET) to catch midnight-boundary matches."""
    et = pytz.timezone("US/Eastern")
    now_et = datetime.now(et)
    yesterday = (now_et - timedelta(days=1)).strftime("%Y%m%d")
    tomorrow = (now_et + timedelta(days=1)).strftime("%Y%m%d")
    return f"{yesterday}-{tomorrow}"

def _normalize_espn(event, competition, status):
    """Normalize ESPN competition data into a clean dict."""
    competitors = competition.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    
    # Fallback if home/away not explicitly tagged
    if not home and len(competitors) > 0:
        home = competitors[0]
    if not away and len(competitors) > 1:
        away = competitors[1]
        
    status_name = status.get("name", "")
    detail = status.get("detail", "")
    
    # Match clock (seconds elapsed in current period)
    full_status = competition.get("status", {})
    clock_seconds = full_status.get("clock", 0)
    period = full_status.get("period", 1)
    
    # Map ESPN status to our status
    if status_name in ("STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "STATUS_EXTRA_TIME", "STATUS_PENALTY_SHOOTOUT", "STATUS_IN_PROGRESS"):
        mapped_status = "IN_PLAY"
    elif status_name == "STATUS_HALFTIME":
        mapped_status = "HALFTIME"
    elif status_name == "STATUS_FULL_TIME":
        mapped_status = "FINISHED"
    elif status_name == "STATUS_SCHEDULED":
        mapped_status = "SCHEDULED"
    else:
        mapped_status = status_name
        
    # Parse event date for display
    event_date = event.get("date", "")
    date_display = ""
    time_et_display = ""
    utc_iso = ""
    if event_date:
        try:
            utc_dt = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
            utc_iso = utc_dt.isoformat()
            et_tz = pytz.timezone("US/Eastern")
            et_dt = utc_dt.astimezone(et_tz)
            date_display = et_dt.strftime("%b %d, %Y")
            time_et_display = et_dt.strftime("%-I:%M %p ET")
        except Exception:
            date_display = event_date
            time_et_display = ""

    # Format display clock
    if mapped_status == "IN_PLAY":
        mins = int(clock_seconds) // 60
        display_clock = f"{mins}'"
    else:
        display_clock = detail if detail else mapped_status

    # Helper to extract stats safely
    def get_stat(stats_list, stat_name):
        for stat in stats_list:
            if stat.get("name") == stat_name:
                val = stat.get("displayValue", "0")
                try:
                    return float(str(val).replace("%", "").replace(",", ""))
                except ValueError:
                    return 0
        return 0

    team_1_stats_list = home.get("statistics", [])
    team_2_stats_list = away.get("statistics", [])
    
    venue = competition.get("venue", {})
    venue_name = venue.get("fullName", "") if isinstance(venue, dict) else str(venue)
    city_name = venue.get("address", {}).get("city", "") if isinstance(venue, dict) and isinstance(venue.get("address"), dict) else ""

    # --- THIS RETURN STATEMENT WAS MISSING IN YOUR FILE ---
    return {
        "team_1_name": home.get("team", {}).get("displayName", home.get("team", {}).get("shortDisplayName", "Team 1")),
        "team_2_name": away.get("team", {}).get("displayName", away.get("team", {}).get("shortDisplayName", "Team 2")),
        "team_1_logo": home.get("team", {}).get("logo", ""),
        "team_2_logo": away.get("team", {}).get("logo", ""),
        "team_1_score": str(home.get("score", "0")),
        "team_2_score": str(away.get("score", "0")),
        "status": mapped_status,
        "clock_seconds": int(clock_seconds) if clock_seconds else 0,
        "period": int(period) if period else 1,
        "display_clock": display_clock,
        "date": date_display,
        "time_et": time_et_display,
        "utc_iso": utc_iso,
        "venue": venue_name,
        "city": city_name,
        "stage": event.get("shortName", event.get("name", "Match")),
        "match_events": [],
        "team_1_stats": {
            "possession": get_stat(team_1_stats_list, "possession"),
            "shots": get_stat(team_1_stats_list, "totalShots"),
            "shots_on_target": get_stat(team_1_stats_list, "shotsOnTarget"),
            "corners": get_stat(team_1_stats_list, "cornerKicks"),
            "fouls": get_stat(team_1_stats_list, "fouls"),
        },
        "team_2_stats": {
            "possession": get_stat(team_2_stats_list, "possession"),
            "shots": get_stat(team_2_stats_list, "totalShots"),
            "shots_on_target": get_stat(team_2_stats_list, "shotsOnTarget"),
            "corners": get_stat(team_2_stats_list, "cornerKicks"),
            "fouls": get_stat(team_2_stats_list, "fouls"),
        }
    }

@st.cache_data(ttl=15)
def get_live_matches():
    """Fetch currently live World Cup matches from ESPN API."""
    date_range = _get_date_range()
    for _attempt in range(3):
        try:
            resp = requests.get(ESPN_API, params={"dates": date_range}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            matches = []
            for event in data.get("events", []):
                comp = event.get("competitions", [{}])[0]
                status = comp.get("status", {}).get("type", {})
                status_name = status.get("name", "")
                # Only return in-progress matches
                if status_name in (
                    "STATUS_FIRST_HALF", "STATUS_SECOND_HALF",
                    "STATUS_HALFTIME", "STATUS_EXTRA_TIME",
                    "STATUS_PENALTY_SHOOTOUT", "STATUS_IN_PROGRESS",
                ):
                    matches.append(_normalize_espn(event, comp, status))
            return matches
        except Exception:
            continue
    return []

@st.cache_data(ttl=60)
def get_upcoming_matches():
    """Fetch upcoming scheduled World Cup matches from ESPN API."""
    try:
        resp = requests.get(
            ESPN_API,
            params={"dates": "20260611-20260719"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        upcoming = []
        for event in data.get("events", []):
            comp = event.get("competitions", [{}])[0]
            status = comp.get("status", {}).get("type", {})
            if status.get("name") == "STATUS_SCHEDULED":
                upcoming.append(_normalize_espn(event, comp, status))
        return upcoming
    except Exception:
        return []

@st.cache_data(ttl=60)
def get_all_results():
    """Fetch all finished World Cup matches from ESPN API."""
    try:
        resp = requests.get(
            ESPN_API,
            params={"dates": "20260611-20260719"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for event in data.get("events", []):
            comp = event.get("competitions", [{}])[0]
            status = comp.get("status", {}).get("type", {})
            if status.get("name") == "STATUS_FULL_TIME":
                results.append(_normalize_espn(event, comp, status))
        return results
    except Exception:
        return []

def _get_group(match):
    if not match:
        return ""
    g = _group_map.get(match.get("team_1_name"))
    if not g:
        g = _group_map.get(match.get("team_2_name"))
    return f"Group {g}" if g else ""

@st.fragment(run_every=10)
@st.fragment(run_every=10)
def _live_section():
    """Auto-refreshing section: stats pills + live match or countdown."""
    _et = timezone("US/Eastern")
    _now = datetime.now(_et)
    _wc_end = _et.localize(datetime(2026, 7, 19, 23, 59, 59))
    _remaining_seconds = max(0, int((_wc_end - _now).total_seconds()))
    _days_left = _remaining_seconds // 86400
    _all_results = get_all_results()
    _matches_played = len(_all_results)
    _games_remaining = 104 - _matches_played
    
    # Tournament stats — metric pills (hidden on mobile via CSS)
    _pill = 'display:inline-block; background:rgba(17,86,117,0.35); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid rgba(41,181,232,0.2); border-radius:20px; padding:0.4rem 1.2rem; margin:0.2rem 0.3rem; width:180px; text-align:center; white-space:nowrap;'
    _pill_val = 'font-size:1.4rem; font-weight:900; color:#FFD700;'
    _pill_lbl = 'font-size:0.75rem; color:#e0e0e0; text-transform:uppercase; letter-spacing:1px;'
    st.markdown(
        f'<style>@media(max-width:768px){{.desktop-pills{{display:none!important}}}}</style>'
        f'<div class="desktop-pills" style="text-align:center; margin:0.5rem 0;">'
        f'<p style="font-size:1.2rem; color:#FFD700; font-weight:800; margin:0 0 0.5rem 0; letter-spacing:1px;">11 June – 19 July 2026</p>'
        f'<span style="{_pill}"><span class="countup" data-target="{_days_left}" style="{_pill_val}">0</span> <span style="{_pill_lbl}">days left</span></span>'
        f'<span style="{_pill}"><span class="countup" data-target="{_games_remaining}" style="{_pill_val}">0</span> <span style="{_pill_lbl}">games left</span></span>'
        f'<span style="{_pill}"><span class="countup" data-target="48" style="{_pill_val}">0</span> <span style="{_pill_lbl}">teams</span></span>'
        f'<span style="{_pill}"><span class="countup" data-target="16" style="{_pill_val}">0</span> <span style="{_pill_lbl}">venues</span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    
    # Count-up animation JS
    st.html(
        '''<script>
        (function(){
        var doc=document;
        var els=doc.querySelectorAll(".countup");
        if(!els.length)return;
        var duration=1500,stagger=1000;
        els.forEach(function(el,i){
        var target=parseInt(el.getAttribute("data-target"));
        setTimeout(function(){
        var start=performance.now();
        function tick(now){
        var t=Math.min((now-start)/duration,1);
        var ease=1-Math.pow(1-t,4);
        el.textContent=Math.round(ease*target);
        if(t<1){ el.style.color="#ffffff"; requestAnimationFrame(tick); }
        else { el.style.color="#FFD700"; }
        }
        requestAnimationFrame(tick);
        }, i*stagger);
        });
        })();
        </script>'''
    )
    
    # Live match display (via ESPN API — real-time)
    live_matches = get_live_matches()
    
    # Persist last known live match to avoid flicker on API gaps
    if live_matches:
        st.session_state["_last_live"] = live_matches[0]
    elif st.session_state.get("_last_live"):
        _finished = {(r["team_1_name"], r["team_2_name"]) for r in get_all_results() if r}
        _cached = st.session_state["_last_live"]
        if (_cached["team_1_name"], _cached["team_2_name"]) in _finished or \
           (_cached["team_2_name"], _cached["team_1_name"]) in _finished:
            del st.session_state["_last_live"]
        else:
            live_matches = [st.session_state["_last_live"]]
            
    if live_matches:
        # --- LIVE MATCH CARD ---
        match = live_matches[0]
        if match["status"] == "HALFTIME":
            badge_html = '<span style="background:#FFD700; color:#000; padding:4px 16px; border-radius:16px; font-size:1rem; font-weight:700;">HALF TIME</span>'
        else:
            badge_html = '<span class="live-badge">● LIVE</span>'
            
        info_parts = []
        group_name = _get_group(match)
        if group_name:
            info_parts.append(group_name)
        else:
            info_parts.append(match["stage"])
        if match.get("venue"):
            venue_str = match["venue"]
            if match.get("city"):
                venue_str += f', {match["city"]}'
            info_parts.append(venue_str)
            
        st.markdown("---")
        st.markdown('<h3 style="text-align:center;">Current Match</h3>', unsafe_allow_html=True)
        
        _clock_secs = match.get("clock_seconds", 0)
        _period = match.get("period", 1)
        _is_halftime = match["status"] == "HALFTIME"
        _display_clock = match.get("display_clock", "")
        
        st.html(
            f'''<style>
            @keyframes pulse {{ 0%{{opacity:1}} 50%{{opacity:0.5}} 100%{{opacity:1}} }}
            .live-badge {{ display:inline-block; background:#FF4B4B; color:white; padding:4px 16px; border-radius:16px; font-size:1rem; font-weight:700; animation:pulse 1.5s infinite; letter-spacing:1px; }}
            .live-card .desktop-layout {{ display:flex; }}
            .live-card .mobile-layout {{ display:none; }}
            .live-card .card-header {{ background:linear-gradient(135deg, #0056b3 0%, #0d4a96 50%, #1a6bb5 100%); border-radius:20px 20px 0 0; padding:1rem 2rem; text-align:center; }}
            @media(max-width:768px){{
            .live-card{{padding:1rem!important}}
            .live-card .desktop-layout {{ display:none; }}
            .live-card .mobile-layout {{ display:block; }}
            }}
            </style>
            <div class="live-card" style="background:rgba(17,86,117,0.25); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border-radius:20px; margin:0; border:1px solid rgba(41,181,232,0.25); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; overflow:hidden;">
            <div class="card-header">{badge_html}</div>
            <div style="padding:2rem 3rem;">
            <div class="desktop-layout" style="justify-content:space-between; align-items:center;">
            <div style="text-align:center; flex:1;">
            <img src="{match['team_1_logo']}" style="height:3rem; margin-bottom:0.5rem;"><br>
            <span style="font-size:1.3rem; font-weight:700; color:#ffffff;">{match['team_1_name']}</span></div>
            <div style="text-align:center; flex:1;">
            <p class="score" style="font-size:4rem; font-weight:900; color:#ffffff; margin:0; line-height:1;">{match['team_1_score']} – {match['team_2_score']}</p>
            <p id="match-clock" style="font-size:1.1rem; font-weight:700; color:#FFD700; margin:0.3rem 0 0 0; font-variant-numeric:tabular-nums;"></p>
            <p style="font-size:0.85rem; color:#e0e0e0; margin:0.3rem 0 0 0;">{" &nbsp;|&nbsp; ".join(info_parts)}</p></div>
            <div style="text-align:center; flex:1;">
            <img src="{match['team_2_logo']}" style="height:3rem; margin-bottom:0.5rem;"><br>
            <span style="font-size:1.3rem; font-weight:700; color:#ffffff;">{match['team_2_name']}</span></div>
            </div>
            <div class="mobile-layout" style="text-align:center;">
            <div style="display:flex; justify-content:center; align-items:center; gap:0.5rem; margin-bottom:0.4rem;">
            <img src="{match['team_1_logo']}" style="height:1.8rem;">
            <span style="font-size:0.9rem; font-weight:700; color:#fff;">{match['team_1_name']}</span>
            <span style="font-size:0.75rem; color:#e0e0e0;">vs</span>
            <img src="{match['team_2_logo']}" style="height:1.8rem;">
            <span style="font-size:0.9rem; font-weight:700; color:#fff;">{match['team_2_name']}</span>
            </div>
            <p style="font-size:2.5rem; font-weight:900; color:#fff; margin:0; line-height:1;">{match['team_1_score']} – {match['team_2_score']}</p>
            <p id="match-clock-m" style="font-size:1rem; font-weight:700; color:#FFD700; margin:0; font-variant-numeric:tabular-nums;"></p>
            <p style="font-size:0.7rem; color:#e0e0e0; margin:0.2rem 0 0 0;">{" &nbsp;|&nbsp; ".join(info_parts)}</p>
            </div>
            </div>
            </div>
            <script>
            (function(){{
            var displayClock="{_display_clock}";
            var halftime={'true' if _is_halftime else 'false'};
            var period={_period};
            var els=[document.getElementById("match-clock"),document.getElementById("match-clock-m")];
            var halfLabel=period===1?"1st Half":"2nd Half";
            function show(txt){{ els.forEach(function(e){{if(e)e.textContent=txt;}}); }}
            if(halftime){{ show("HT"); }}
            else {{ show(displayClock+" \\u2022 "+halfLabel); }}
            }})();
            </script>'''
        )
        
        # --- Live Match Stats ---
        _s1 = match.get("team_1_stats", {})
        _s2 = match.get("team_2_stats", {})
        _events = match.get("match_events", [])
        
        if _s1.get("possession", 0) > 0 or _s2.get("possession", 0) > 0:
            _poss1 = _s1.get("possession", 0)
            _poss2 = _s2.get("possession", 0)
            _shots1 = _s1.get("shots", 0)
            _shots2 = _s2.get("shots", 0)
            _sot1 = _s1.get("shots_on_target", 0)
            _sot2 = _s2.get("shots_on_target", 0)
            _corners1 = _s1.get("corners", 0)
            _corners2 = _s2.get("corners", 0)
            _fouls1 = _s1.get("fouls", 0)
            _fouls2 = _s2.get("fouls", 0)
            
            _events_html = ""
            if _events:
                _event_items = []
                for ev in _events:
                    if ev["type"] == "goal":
                        icon = "⚽"
                    elif ev["type"] == "own_goal":
                        icon = "🔴"
                    elif ev["type"] == "red":
                        icon = ""
                    else:
                        icon = ""
                    side_color = "#ffffff" if ev["side"] == 1 else "#e0e0e0"
                    _event_items.append(
                        f'<span style="display:inline-block; margin:0.15rem 0.3rem; padding:0.2rem 0.5rem; '
                        f'background:rgba(17,86,117,0.4); border-radius:6px; font-size:0.7rem; color:{side_color};">'
                        f'{icon} {ev["minute"]} {ev["player"]}</span>'
                    )
                _events_html = f'<div style="text-align:center; margin-top:0.6rem;">{"".join(_event_items)}</div>'
                
            st.markdown(
                f'<style>'
                f'@keyframes statPop {{ from {{ opacity:0; transform:scale(0.8); }} to {{ opacity:1; transform:scale(1); }} }}'
                f'@keyframes barGrow {{ from {{ width:0%; }} to {{ width:{_poss1}%; }} }}'
                f'.stat-pill {{ display:inline-block; background:rgba(17,86,117,0.4); backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); '
                f'border:1px solid rgba(41,181,232,0.2); border-radius:20px; padding:0.4rem 1rem; margin:0.2rem; text-align:center; '
                f'animation:statPop 0.5s ease backwards; min-width:80px; }}'
                f'.stat-pill:nth-child(1) {{ animation-delay:0.1s; }}'
                f'.stat-pill:nth-child(2) {{ animation-delay:0.2s; }}'
                f'.stat-pill:nth-child(3) {{ animation-delay:0.3s; }}'
                f'.stat-pill:nth-child(4) {{ animation-delay:0.4s; }}'
                f'.stat-pill .val {{ font-size:1.2rem; font-weight:900; color:#FFD700; }}'
                f'.stat-pill .lbl {{ font-size:0.6rem; color:#e0e0e0; text-transform:uppercase; letter-spacing:0.5px; }}'
                f'@media(max-width:768px){{ .stat-row .stat-left {{ justify-content:flex-end!important; }} .stat-row .stat-right {{ justify-content:flex-start!important; }} }}'
                f'</style>'
                f'<div style="background:rgba(17,86,117,0.2); backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); '
                f'border-radius:14px; padding:1rem 1.5rem; margin:0.5rem 0; border:1px solid rgba(41,181,232,0.15);">'
                f'<div style="display:flex; justify-content:center; align-items:center; gap:0.5rem; margin-bottom:0.8rem;">'
                f'<div class="stat-pill"><div class="val">{_poss1:.0f}%</div><div class="lbl">Possession</div></div>'
                f'<div style="display:flex; flex:1; height:8px; border-radius:4px; overflow:hidden; box-shadow:0 0 10px rgba(41,181,232,0.2);">'
                f'<div style="width:{_poss1}%; background:linear-gradient(90deg, #29B5E8, #115675); transition:width 1s ease;"></div>'
                f'<div style="width:{_poss2}%; background:rgba(255,255,255,0.2);"></div>'
                f'</div>'
                f'<div class="stat-pill"><div class="val">{_poss2:.0f}%</div><div class="lbl">Possession</div></div>'
                f'</div>'
                f'<div class="stat-row" style="display:flex; justify-content:center; align-items:center; gap:0.5rem;">'
                f'<div class="stat-left" style="display:flex; gap:0.3rem; flex-wrap:wrap; justify-content:center;">'
                f'<div class="stat-pill"><div class="val">{_shots1}</div><div class="lbl">Shots</div></div>'
                f'<div class="stat-pill"><div class="val">{_sot1}</div><div class="lbl">On Target</div></div>'
                f'<div class="stat-pill"><div class="val">{_corners1}</div><div class="lbl">Corners</div></div>'
                f'<div class="stat-pill"><div class="val">{_fouls1}</div><div class="lbl">Fouls</div></div>'
                f'</div>'
                f'<div class="stat-divider" style="width:2px; height:50px; background:rgba(255,215,0,0.5); border-radius:1px; flex-shrink:0;"></div>'
                f'<div class="stat-right" style="display:flex; gap:0.3rem; flex-wrap:wrap; justify-content:center;">'
                f'<div class="stat-pill"><div class="val">{_shots2}</div><div class="lbl">Shots</div></div>'
                f'<div class="stat-pill"><div class="val">{_sot2}</div><div class="lbl">On Target</div></div>'
                f'<div class="stat-pill"><div class="val">{_corners2}</div><div class="lbl">Corners</div></div>'
                f'<div class="stat-pill"><div class="val">{_fouls2}</div><div class="lbl">Fouls</div></div>'
                f'</div>'
                f'</div>'
                f'{_events_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        # --- NEXT MATCH COUNTDOWN (when no live matches) ---
        _upcoming = get_upcoming_matches()
        if _upcoming:
            next_match = _upcoming[0]
            
            _next_match_time = None
            if next_match and next_match.get("utc_iso"):
                try:
                    _next_match_time = datetime.fromisoformat(next_match["utc_iso"]).astimezone(_et)
                except Exception:
                    _next_match_time = None
                    
            st.markdown("---")
            st.markdown('<h3 style="text-align:center;">Next Match</h3>', unsafe_allow_html=True)
            
            _target_iso = ""
            _countdown_active = False
            if _next_match_time:
                _target_iso = _next_match_time.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                _countdown_active = _next_match_time > _now
                
            _info_line1 = next_match.get("date", "")
            if next_match.get("time_et"):
                _info_line1 += f' at {next_match["time_et"]}'
                
            _info_line2_parts = []
            group_name = _get_group(next_match)
            if group_name:
                _info_line2_parts.append(group_name)
            if next_match.get("venue"):
                venue_str = next_match["venue"]
                if next_match.get("city"):
                    venue_str += f', {next_match["city"]}'
                _info_line2_parts.append(venue_str)
            _info_line2 = " | ".join(_info_line2_parts)
            
            if _countdown_active:
                st.html(
                    f'''<style>
                    .cd-card .desktop-layout {{ display:flex; }}
                    .cd-card .mobile-layout {{ display:none; }}
                    .cd-card .card-header {{ background:linear-gradient(135deg, #0056b3 0%, #0d4a96 50%, #1a6bb5 100%); border-radius:20px 20px 0 0; padding:1rem 2rem; text-align:center; }}
                    @media(max-width:768px){{
                    .cd-card{{padding:1rem!important}}
                    .cd-card .desktop-layout {{ display:none; }}
                    .cd-card .mobile-layout {{ display:block; }}
                    }}
                    </style>
                    <div class="cd-card" style="background:rgba(17,86,117,0.25); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border-radius:20px; margin:0; border:1px solid rgba(41,181,232,0.25); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; overflow:hidden;">
                    <div class="card-header">
                    <p style="font-size:1.2rem; font-weight:700; color:#FFD700; margin:0; letter-spacing:1px;">⏰ NEXT MATCH COUNTDOWN</p>
                    </div>
                    <div style="padding:2rem 3rem;">
                    <div class="desktop-layout" style="justify-content:space-between; align-items:center;">
                    <div style="text-align:center; flex:1;">
                    <img src="{next_match['team_1_logo']}" style="height:3rem; margin-bottom:0.5rem;"><br>
                    <span style="font-size:1.3rem; font-weight:700; color:#ffffff;">{next_match['team_1_name']}</span></div>
                    <div style="text-align:center; flex:1;">
                    <p id="cd" style="font-size:3.5rem; font-weight:900; color:#FFD700; margin:0; line-height:1; font-variant-numeric:tabular-nums;">--:--:--</p>
                    <p style="font-size:0.85rem; color:#e0e0e0; margin:0.3rem 0 0 0;">{_info_line1}</p>
                    <p style="font-size:0.85rem; color:#e0e0e0; margin:0.1rem 0 0 0;">{_info_line2}</p></div>
                    <div style="text-align:center; flex:1;">
                    <img src="{next_match['team_2_logo']}" style="height:3rem; margin-bottom:0.5rem;"><br>
                    <span style="font-size:1.3rem; font-weight:700; color:#ffffff;">{next_match['team_2_name']}</span></div>
                    </div>
                    <div class="mobile-layout" style="text-align:center;">
                    <div style="display:flex; justify-content:center; align-items:center; gap:0.5rem; margin-bottom:0.4rem;">
                    <img src="{next_match['team_1_logo']}" style="height:1.8rem;">
                    <span style="font-size:0.95rem; font-weight:700; color:#fff;">{next_match['team_1_name']}</span>
                    <span style="font-size:0.8rem; color:#e0e0e0;">vs</span>
                    <img src="{next_match['team_2_logo']}" style="height:1.8rem;">
                    <span style="font-size:0.95rem; font-weight:700; color:#fff;">{next_match['team_2_name']}</span>
                    </div>
                    <p id="cd-m" style="font-size:2.2rem; font-weight:900; color:#FFD700; margin:0; line-height:1.2; font-variant-numeric:tabular-nums;">--:--:--</p>
                    <p style="font-size:0.7rem; color:#e0e0e0; margin:0.2rem 0 0 0;">{_info_line1}</p>
                    <p style="font-size:0.7rem; color:#e0e0e0; margin:0.1rem 0 0 0;">{_info_line2}</p>
                    </div>
                    </div>
                    </div>
                    <script>
                    (function(){{
                    var target=new Date("{_target_iso}").getTime();
                    var els=[document.getElementById("cd"),document.getElementById("cd-m")];
                    function tick(){{
                    var diff=Math.max(0,Math.floor((target-Date.now())/1000));
                    var d=Math.floor(diff/86400),h=Math.floor((diff%86400)/3600),m=Math.floor((diff%3600)/60),s=diff%60;
                    var t=d>0?d+"d "+String(h).padStart(2,"0")+":"+String(m).padStart(2,"0")+":"+String(s).padStart(2,"0"):String(h).padStart(2,"0")+":"+String(m).padStart(2,"0")+":"+String(s).padStart(2,"0");
                    els.forEach(function(e){{if(e)e.textContent=t;}});
                    }}
                    tick();setInterval(tick,1000);
                    }})();
                    </script>'''
                )
            else:
                st.html(
                    f'''<style>
                    @keyframes kickPulse {{ 0%{{opacity:1}} 50%{{opacity:0.5}} 100%{{opacity:1}} }}
                    .ko-card .desktop-layout {{ display:flex; }}
                    .ko-card .mobile-layout {{ display:none; }}
                    .ko-card .card-header {{ background:linear-gradient(135deg, #0056b3 0%, #0d4a96 50%, #1a6bb5 100%); border-radius:20px 20px 0 0; padding:1rem 2rem; text-align:center; }}
                    @media(max-width:768px){{
                    .ko-card{{padding:1rem!important}}
                    .ko-card .desktop-layout {{ display:none; }}
                    .ko-card .mobile-layout {{ display:block; }}
                    }}
                    </style>
                    <div class="ko-card" style="background:rgba(17,86,117,0.25); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border-radius:20px; margin:0; border:1px solid rgba(41,181,232,0.25); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; overflow:hidden;">
                    <div class="card-header">
                    <p style="font-size:1.2rem; font-weight:700; color:#FFD700; margin:0; letter-spacing:1px;">⚽ KICKOFF IMMINENT</p>
                    </div>
                    <div style="padding:2rem 3rem;">
                    <div class="desktop-layout" style="justify-content:space-between; align-items:center;">
                    <div style="text-align:center; flex:1;">
                    <img src="{next_match['team_1_logo']}" style="height:3rem; margin-bottom:0.5rem;"><br>
                    <span style="font-size:1.3rem; font-weight:700; color:#ffffff;">{next_match['team_1_name']}</span></div>
                    <div style="text-align:center; flex:1;">
                    <p style="font-size:2rem; font-weight:900; color:#FFD700; margin:0; line-height:1; animation:kickPulse 1.5s infinite;">&#9917; KICKOFF</p>
                    <p style="font-size:0.85rem; color:#e0e0e0; margin:0.3rem 0 0 0;">{_info_line1}</p>
                    <p style="font-size:0.85rem; color:#e0e0e0; margin:0.1rem 0 0 0;">{_info_line2}</p></div>
                    <div style="text-align:center; flex:1;">
                    <img src="{next_match['team_2_logo']}" style="height:3rem; margin-bottom:0.5rem;"><br>
                    <span style="font-size:1.3rem; font-weight:700; color:#ffffff;">{next_match['team_2_name']}</span></div>
                    </div>
                    <div class="mobile-layout" style="text-align:center;">
                    <p style="font-size:1.4rem; font-weight:900; color:#FFD700; margin:0 0 0.5rem 0; animation:kickPulse 1.5s infinite;">&#9917; KICKOFF</p>
                    <div style="display:flex; justify-content:center; align-items:center; gap:0.8rem; margin-bottom:0.3rem;">
                    <img src="{next_match['team_1_logo']}" style="height:1.8rem;">
                    <span style="font-size:0.95rem; font-weight:700; color:#fff;">{next_match['team_1_name']}</span>
                    <span style="font-size:0.8rem; color:#e0e0e0;">vs</span>
                    <img src="{next_match['team_2_logo']}" style="height:1.8rem;">
                    <span style="font-size:0.95rem; font-weight:700; color:#fff;">{next_match['team_2_name']}</span>
                    </div>
                    <p style="font-size:0.7rem; color:#e0e0e0; margin:0.2rem 0 0 0;">{_info_line1}</p>
                    <p style="font-size:0.7rem; color:#e0e0e0; margin:0.1rem 0 0 0;">{_info_line2}</p>
                    </div>
                    </div>
                    </div>'''
                )

#---------------------------------------------------------------------------------------------------------------------------------
### Main app
#---------------------------------------------------------------------------------------------------------------------------------
# Load team-to-group mapping from Snowflake
_group_map = {}
try:
    _teams_df = run_query("SELECT TEAM_NAME, GROUP_LETTER FROM TEAMS")
    _group_map = dict(zip(_teams_df["TEAM_NAME"], _teams_df["GROUP_LETTER"]))
except Exception:
    pass

# Render the auto-refreshing fragment
_live_section()

# --- Static content below (only reruns on full page load) ---
# Full schedule expander
_upcoming_static = get_upcoming_matches()
if _upcoming_static and len(_upcoming_static) > 1:
    # Added defensive 'if m' check to prevent crashes if API ever returns unexpected data
    _schedule = [m for m in _upcoming_static[1:] if m and "Winner" not in m.get("team_1_name", "") and "Winner" not in m.get("team_2_name", "")]
    if _schedule:
        with st.expander("📅 Full Upcoming Schedule"):
            schedule_data = []
            for m in _schedule:
                g = _get_group(m) or ""
                date_str = m.get("date", "")
                time_str = m.get("time_et", "").replace(" ET", "")
                if time_str:
                    date_str += f" {time_str}"
                schedule_data.append({
                    "Date": date_str,
                    "Match": f"{m['team_1_name']} vs {m['team_2_name']}",
                    "Group": g,
                })
            df = pd.DataFrame(schedule_data)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=400,
            )
        st.markdown("---")

# Past Matches section (all results as dataframe in expander)
_all_results_static = get_all_results()
if _all_results_static:
    with st.expander("📋 Past Match Results"):
        results_data = []
        for m in reversed(_all_results_static):  # most recent first
            if not m:
                continue
            g = _get_group(m) or m.get("stage", "")
            date_str = m.get("date", "")
            results_data.append({
                "Date": date_str,
                "Result": f"{m['team_1_name']} {m['team_1_score']} – {m['team_2_score']} {m['team_2_name']}",
                "Group": g,
            })
        df = pd.DataFrame(results_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=400,
        )
    st.markdown("---")
