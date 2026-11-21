import streamlit as st
import random
import folium
import json
import os
import re
import base64
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from streamlit_folium import st_folium
from folium.features import DivIcon
from collections import Counter

CENTRAL_TZ = ZoneInfo("America/Chicago")

st.set_page_config(layout="wide", page_title="RAGBRAI: The Game")

PROFILES_DIR = "profiles"
os.makedirs(PROFILES_DIR, exist_ok=True)


def get_profile_path(username):
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', username.strip().lower())
    return os.path.join(PROFILES_DIR, f"{safe_name}.json")


def default_profile(display_name):
    return {
        "display_name": display_name,
        "completed_towns": [],
        "games_finished": 0,
        "standard_wins": 0,
        "ragbraile_days_solved": [],
        "ragbraile_results": {},
        "best_score": 0,
        "total_score_sum": 0,
        "best_ragbraile_score": 0,
        "ragbraile_score_sum": 0,
        "ragbraile_completions_count": 0,
        "total_miles_ridden": 0,
        "current_streak": 0,
        "last_solved_date": None,
        "recent_routes": [],
        "active_ragbraile": None
    }


def _get_github_config():
    try:
        token = st.secrets.get("GITHUB_TOKEN", "").strip()
        repo = st.secrets.get("GITHUB_REPO", "").strip()
        branch = st.secrets.get("GITHUB_BRANCH", "main").strip()
        return token, repo, branch
    except Exception:
        return "", "", "main"


def _github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "RAGBRAI-The-Game"
    }


def _github_contents_urls(username, repo, branch):
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', username.strip().lower())
    base_url = f"https://api.github.com/repos/{repo}/contents/profiles/{safe_name}.json"
    return f"{base_url}?ref={branch}", base_url


def load_user_profile(username):
    token, repo, branch = _get_github_config()
    if token and repo:
        get_url, _ = _github_contents_urls(username, repo, branch)
        req = urllib.request.Request(get_url, headers=_github_headers(token), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                decoded = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
                base = default_profile(username)
                base.update(decoded)
                if not isinstance(base.get("ragbraile_results"), dict):
                    base["ragbraile_results"] = {}
                return base, True
        except urllib.error.HTTPError as e:
            if e.code != 404:
                st.warning(f"GitHub profile load warning ({e.code}); initializing profile.")
        except Exception:
            pass

        new_prof = default_profile(username)
        save_user_profile(username, new_prof)
        return new_prof, False

    path = get_profile_path(username)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                base = default_profile(username)
                base.update(data)
                if not isinstance(base.get("ragbraile_results"), dict):
                    base["ragbraile_results"] = {}
                return base, True
        except Exception:
            pass
    new_prof = default_profile(username)
    save_user_profile(username, new_prof)
    return new_prof, False


def save_user_profile(username, profile):
    if not username:
        return

    token, repo, branch = _get_github_config()
    if token and repo:
        get_url, put_url = _github_contents_urls(username, repo, branch)
        existing_sha = None
        try:
            get_req = urllib.request.Request(get_url, headers=_github_headers(token), method="GET")
            with urllib.request.urlopen(get_req, timeout=10) as resp:
                existing_sha = json.loads(resp.read().decode("utf-8")).get("sha")
        except Exception:
            pass

        raw_bytes = json.dumps(profile, indent=4).encode("utf-8")
        body = {
            "message": f"Update profile for {username}",
            "content": base64.b64encode(raw_bytes).decode("utf-8"),
            "branch": branch
        }
        if existing_sha:
            body["sha"] = existing_sha

        put_req = urllib.request.Request(
            put_url,
            data=json.dumps(body).encode("utf-8"),
            headers=_github_headers(token),
            method="PUT"
        )
        try:
            with urllib.request.urlopen(put_req, timeout=10):
                return
        except urllib.error.HTTPError as e:
            st.error(f"Could not save profile to GitHub (HTTP {e.code}). Check token permissions.")
        except Exception as e:
            st.error(f"Could not save profile to GitHub: {e}")

    path = get_profile_path(username)
    try:
        with open(path, "w") as f:
            json.dump(profile, f, indent=4)
    except Exception:
        pass


# --- CONSTANTS & DATA ---
START_TOWNS = [
    "Sioux City", "Council Bluffs", "Hawarden", "Onawa", "Glenwood", 
    "Missouri Valley", "Sioux Center", "Le Mars", "Orange City", "Sidney"
]

FINISH_TOWNS = [
    "Fort Madison", "Burlington", "Keokuk", "Muscatine", "Clinton", 
    "Bellevue", "Guttenberg", "Dubuque", "Lansing", "Davenport"
]

TOWN_HISTORY_DATA = {
    "Sioux City": {"count": 8, "last": "2023"}, "Council Bluffs": {"count": 7, "last": "2019"},
    "Hawarden": {"count": 3, "last": "1998"}, "Onawa": {"count": 7, "last": "2026"},
    "Glenwood": {"count": 8, "last": "2024"}, "Missouri Valley": {"count": 4, "last": "2008"},
    "Sioux Center": {"count": 4, "last": "2012"}, "Le Mars": {"count": 2, "last": "2021"},
    "Orange City": {"count": 2, "last": "2025"}, "Sidney": {"count": 1, "last": "1976"},
    "Storm Lake": {"count": 7, "last": "2023"}, "Cherokee": {"count": 5, "last": "2012"},
    "Red Oak": {"count": 5, "last": "2024"}, "Shenandoah": {"count": 4, "last": "2016"},
    "Harlan": {"count": 7, "last": "2026"}, "Greenfield": {"count": 3, "last": "2009"},
    "Sheldon": {"count": 2, "last": "2005"}, "Denison": {"count": 3, "last": "2018"},
    "Lake View": {"count": 4, "last": "2012"}, "Carroll": {"count": 5, "last": "2023"},
    "Atlantic": {"count": 8, "last": "2024"}, "Clarinda": {"count": 1, "last": "1989"},
    "Milford": {"count": 1, "last": "2025"}, "Primghar": {"count": 0, "last": "N/A"},
    "Ida Grove": {"count": 4, "last": "2022"}, "Fort Dodge": {"count": 6, "last": "2021"},
    "Algona": {"count": 6, "last": "2017"}, "Estherville": {"count": 4, "last": "2025"},
    "Emmetsburg": {"count": 5, "last": "2022"}, "Creston": {"count": 3, "last": "2016"},
    "Winterset": {"count": 3, "last": "2024"}, "Bedford": {"count": 2, "last": "2003"},
    "Guthrie Center": {"count": 2, "last": "2026"}, "Indianola": {"count": 2, "last": "2019"},
    "Ankeny": {"count": 1, "last": "2000"}, "Osceola": {"count": 2, "last": "2003"},
    "Spencer": {"count": 5, "last": "2017"}, "Boone": {"count": 5, "last": "2026"},
    "Webster City": {"count": 2, "last": "2012"}, "Ames": {"count": 5, "last": "2023"},
    "Perry": {"count": 5, "last": "2013"}, "Mt Ayr": {"count": 0, "last": "N/A"},
    "Forest City": {"count": 5, "last": "2025"}, "Iowa Falls": {"count": 5, "last": "2025"},
    "Clear Lake": {"count": 4, "last": "2017"}, "Humboldt": {"count": 3, "last": "2007"},
    "Des Moines": {"count": 6, "last": "2023"}, "Leon": {"count": 2, "last": "2016"},
    "Knoxville": {"count": 4, "last": "2024"}, "Oskaloosa": {"count": 4, "last": "2013"},
    "Pella": {"count": 1, "last": "1984"}, "Ottumwa": {"count": 5, "last": "2024"},
    "Grinnell": {"count": 4, "last": "2011"}, "Marshalltown": {"count": 5, "last": "2026"},
    "Newton": {"count": 3, "last": "2018"}, "Chariton": {"count": 2, "last": "2009"},
    "Mason City": {"count": 3, "last": "2022"}, "Charles City": {"count": 6, "last": "2022"},
    "Osage": {"count": 2, "last": "1993"}, "Cedar Falls": {"count": 5, "last": "2025"},
    "Waterloo": {"count": 4, "last": "2021"}, "Tama": {"count": 4, "last": "2023"},
    "Waverly": {"count": 3, "last": "2014"}, "Hampton": {"count": 2, "last": "2007"},
    "Centerville": {"count": 3, "last": "2019"}, "Albia": {"count": 0, "last": "N/A"},
    "Fairfield": {"count": 5, "last": "2019"}, "Bloomfield": {"count": 2, "last": "2003"},
    "Mt Pleasant": {"count": 6, "last": "2024"}, "Sigourney": {"count": 3, "last": "2018"},
    "Washington": {"count": 4, "last": "2016"}, "Iowa City": {"count": 2, "last": "2018"},
    "Cedar Rapids": {"count": 2, "last": "2012"}, "Independence": {"count": 4, "last": "2026"},
    "New Hampton": {"count": 1, "last": "1977"}, "Oelwein": {"count": 3, "last": "2025"},
    "Cresco": {"count": 3, "last": "2017"}, "Decorah": {"count": 3, "last": "1999"},
    "Manchester": {"count": 4, "last": "2010"}, "Monticello": {"count": 3, "last": "1998"},
    "Marengo": {"count": 1, "last": "2006"}, "Dyersville": {"count": 3, "last": "2026"},
    "West Union": {"count": 3, "last": "2022"}, "Parkersburg": {"count": 0, "last": "N/A"},
    "Keosauqua": {"count": 1, "last": "1981"}, "Anamosa": {"count": 4, "last": "2021"},
    "Maquoketa": {"count": 3, "last": "2004"}, "Elkader": {"count": 1, "last": "1980"},
    "Coralville": {"count": 6, "last": "2023"}, "Fort Madison": {"count": 5, "last": "2013"},
    "Burlington": {"count": 7, "last": "2024"}, "Keokuk": {"count": 3, "last": "2019"},
    "Muscatine": {"count": 6, "last": "2016"}, "Clinton": {"count": 6, "last": "2021"},
    "Bellevue": {"count": 5, "last": "2007"}, "Guttenberg": {"count": 6, "last": "2025"},
    "Dubuque": {"count": 5, "last": "2026"}, "Lansing": {"count": 3, "last": "2022"},
    "Davenport": {"count": 6, "last": "2023"}
}

TOWN_COORDS = {
    "Sioux City": (42.5006, -96.4003), "Council Bluffs": (41.2619, -95.8608),
    "Hawarden": (43.0033, -96.4864), "Onawa": (42.0294, -96.0958),
    "Glenwood": (41.0494, -95.7428), "Missouri Valley": (41.5564, -95.8886),
    "Sioux Center": (43.0805, -96.1661), "Le Mars": (42.7942, -96.1647),
    "Orange City": (42.9997, -96.0608), "Sidney": (40.7486, -95.6558),
    "Storm Lake": (42.6453, -95.2092), "Cherokee": (42.7514, -95.5539),
    "Red Oak": (41.0117, -95.2289), "Shenandoah": (40.7631, -95.3644),
    "Harlan": (41.6517, -95.3275), "Greenfield": (41.3097, -94.4611),
    "Sheldon": (43.1847, -95.8525), "Denison": (42.0211, -95.3533),
    "Lake View": (42.3047, -95.0411), "Carroll": (42.0678, -94.8647),
    "Atlantic": (41.4039, -95.0069), "Clarinda": (40.7439, -95.0397),
    "Milford": (43.3161, -95.1528), "Primghar": (43.0858, -95.6358),
    "Ida Grove": (42.3486, -95.4719), "Fort Dodge": (42.5042, -94.1717),
    "Algona": (43.0769, -94.2272), "Estherville": (43.4025, -94.8317),
    "Emmetsburg": (43.1114, -94.6708), "Creston": (41.0597, -94.3614),
    "Winterset": (41.3342, -94.0111), "Bedford": (40.6672, -94.7172),
    "Guthrie Center": (41.6853, -94.5078), "Indianola": (41.3578, -93.5578),
    "Ankeny": (41.7303, -93.6097), "Osceola": (41.0336, -93.7642),
    "Spencer": (43.1436, -95.1436), "Boone": (42.0531, -93.8778),
    "Webster City": (42.4672, -93.8153), "Ames": (42.0308, -93.6319),
    "Perry": (41.8417, -94.1039), "Mt Ayr": (40.7169, -94.2422),
    "Forest City": (43.2589, -93.6367), "Iowa Falls": (42.5208, -93.2611),
    "Clear Lake": (43.1383, -93.3769), "Humboldt": (42.7208, -94.2139),
    "Des Moines": (41.5868, -93.625), "Leon": (40.7431, -93.7314),
    "Knoxville": (41.3178, -93.1092), "Oskaloosa": (41.2981, -92.6442),
    "Pella": (41.4089, -92.9158), "Ottumwa": (41.0111, -92.4139),
    "Grinnell": (41.7433, -92.7214), "Marshalltown": (42.0497, -92.9081),
    "Newton": (41.6931, -93.0456), "Chariton": (41.0186, -93.3103),
    "Mason City": (43.1536, -93.2017), "Charles City": (43.0692, -92.6744),
    "Osage": (43.2806, -92.8128), "Cedar Falls": (42.5349, -92.4453),
    "Waterloo": (42.4928, -92.3426), "Tama": (41.9564, -92.5794),
    "Waverly": (42.7258, -92.4772), "Hampton": (42.7458, -93.2131),
    "Centerville": (40.7297, -92.8647), "Albia": (41.0264, -92.8094),
    "Fairfield": (41.0106, -91.9625), "Bloomfield": (40.7453, -92.4111),
    "Mt Pleasant": (40.9703, -91.5542), "Sigourney": (41.3342, -92.2044),
    "Washington": (41.2989, -91.6917), "Iowa City": (41.6611, -91.5302),
    "Cedar Rapids": (41.9779, -91.6656), "Independence": (42.4706, -91.8936),
    "New Hampton": (43.0636, -92.3131), "Oelwein": (42.6789, -91.9125),
    "Cresco": (43.3703, -92.1103), "Decorah": (43.3033, -91.7856),
    "Manchester": (42.4864, -91.4608), "Monticello": (42.2425, -91.1917),
    "Marengo": (41.8028, -92.0747), "Dyersville": (42.4839, -91.1239),
    "West Union": (42.9619, -91.8078), "Parkersburg": (42.5739, -92.7933),
    "Keosauqua": (40.7328, -91.9619), "Anamosa": (42.1114, -91.2783),
    "Maquoketa": (42.0758, -90.6669), "Elkader": (42.8572, -91.3961),
    "Coralville": (41.6772, -91.5878), "Fort Madison": (40.6278, -91.3133),
    "Burlington": (40.8083, -91.1128), "Keokuk": (40.3986, -91.3831),
    "Muscatine": (41.4257, -91.0477), "Clinton": (41.8464, -90.1911),
    "Bellevue": (42.2625, -90.4319), "Guttenberg": (42.7872, -91.1017),
    "Dubuque": (42.5006, -90.6646), "Lansing": (43.3642, -91.2178),
    "Davenport": (41.5236, -90.5776)
}

RAGBRAI_MAP = {
    "Sioux City": {"Storm Lake": 70, "Cherokee": 55, "Orange City": 42, "Le Mars": 26},
    "Council Bluffs": {"Red Oak": 50, "Shenandoah": 59, "Harlan": 47, "Greenfield": 85},
    "Hawarden": {"Cherokee": 63, "Le Mars": 30, "Sheldon": 41, "Storm Lake": 83},
    "Onawa": {"Harlan": 57, "Denison": 43, "Lake View": 66, "Carroll": 70},
    "Glenwood": {"Red Oak": 28, "Shenandoah": 37, "Atlantic": 60, "Clarinda": 55},
    "Missouri Valley": {"Harlan": 34, "Red Oak": 75, "Atlantic": 54, "Denison": 45},
    "Sioux Center": {"Cherokee": 53, "Milford": 68, "Primghar": 30, "Storm Lake": 73},
    "Le Mars": {"Sheldon": 34, "Storm Lake": 54, "Milford": 79, "Ida Grove": 67},
    "Orange City": {"Milford": 65, "Cherokee": 42, "Ida Grove": 75, "Sheldon": 20},
    "Sidney": {"Red Oak": 43, "Clarinda": 35, "Atlantic": 77, "Bedford": 56},
    "Storm Lake": {"Carroll": 56, "Fort Dodge": 62, "Algona": 79, "Lake View": 30},
    "Cherokee": {"Lake View": 53, "Estherville": 81, "Emmetsburg": 71, "Storm Lake": 21},
    "Red Oak": {"Creston": 49, "Atlantic": 36, "Greenfield": 62, "Winterset": 86},
    "Shenandoah": {"Creston": 69, "Bedford": 40, "Atlantic": 58, "Red Oak": 23},
    "Harlan": {"Carroll": 52, "Greenfield": 71, "Atlantic": 32, "Guthrie Center": 45},
    "Greenfield": {"Indianola": 50, "Ankeny": 70, "Winterset": 25, "Osceola": 55},
    "Sheldon": {"Estherville": 64, "Milford": 44, "Spencer": 39, "Storm Lake": 70},
    "Denison": {"Storm Lake": 51, "Carroll": 28, "Guthrie Center": 66, "Boone": 81},
    "Lake View": {"Fort Dodge": 54, "Carroll": 26, "Webster City": 75, "Guthrie Center": 70},
    "Carroll": {"Boone": 53, "Ames": 67, "Guthrie Center": 45, "Ankeny": 85},
    "Atlantic": {"Winterset": 65, "Creston": 58, "Greenfield": 40, "Perry": 77},
    "Clarinda": {"Creston": 54, "Osceola": 86, "Bedford": 20, "Mt Ayr": 48},
    "Milford": {"Estherville": 21, "Emmetsburg": 37, "Algona": 63, "Forest City": 83},
    "Primghar": {"Storm Lake": 48, "Estherville": 62, "Spencer": 29, "Algona": 79},
    "Ida Grove": {"Carroll": 49, "Storm Lake": 34, "Lake View": 22, "Fort Dodge": 77},
    "Fort Dodge": {"Iowa Falls": 51, "Forest City": 80, "Ames": 60, "Webster City": 20},
    "Algona": {"Clear Lake": 45, "Webster City": 63, "Humboldt": 25, "Iowa Falls": 88},
    "Estherville": {"Forest City": 69, "Algona": 51, "Emmetsburg": 25, "Humboldt": 76},
    "Emmetsburg": {"Clear Lake": 68, "Humboldt": 50, "Webster City": 88, "Algona": 25},
    "Creston": {"Osceola": 33, "Indianola": 62, "Des Moines": 71, "Leon": 53},
    "Winterset": {"Indianola": 26, "Knoxville": 51, "Des Moines": 37, "Oskaloosa": 76},
    "Bedford": {"Creston": 43, "Osceola": 73, "Leon": 55, "Mt Ayr": 29},
    "Guthrie Center": {"Boone": 58, "Ames": 72, "Perry": 31, "Winterset": 50},
    "Indianola": {"Knoxville": 25, "Pella": 38, "Oskaloosa": 50, "Ottumwa": 74},
    "Ankeny": {"Newton": 35, "Marshalltown": 45, "Oskaloosa": 69, "Grinnell": 55},
    "Osceola": {"Albia": 52, "Centerville": 66, "Ottumwa": 73, "Indianola": 28},
    "Spencer": {"Algona": 51, "Emmetsburg": 26, "Humboldt": 76, "Estherville": 34},
    "Boone": {"Iowa Falls": 64, "Marshalltown": 54, "Ankeny": 36, "Grinnell": 80},
    "Webster City": {"Marshalltown": 74, "Iowa Falls": 31, "Ankeny": 66, "Ames": 40},
    "Ames": {"Marshalltown": 42, "Pella": 76, "Newton": 54, "Des Moines": 37},
    "Perry": {"Ankeny": 32, "Newton": 65, "Pella": 82, "Ames": 42},
    "Mt Ayr": {"Leon": 26, "Osceola": 44, "Chariton": 68, "Indianola": 78},
    "Forest City": {"Iowa Falls": 70, "Mason City": 29, "Charles City": 63, "Osage": 43},
    "Iowa Falls": {"Cedar Falls": 49, "Charles City": 68, "Waterloo": 55, "Tama": 75},
    "Clear Lake": {"Charles City": 41, "Iowa Falls": 52, "Waverly": 73, "Cedar Falls": 85},
    "Humboldt": {"Mason City": 79, "Iowa Falls": 64, "Webster City": 39, "Hampton": 55},
    "Des Moines": {"Marshalltown": 52, "Newton": 33, "Ottumwa": 85, "Oskaloosa": 60},
    "Leon": {"Chariton": 41, "Centerville": 47, "Albia": 67, "Pella": 83},
    "Knoxville": {"Ottumwa": 48, "Fairfield": 76, "Bloomfield": 67, "Oskaloosa": 25},
    "Oskaloosa": {"Ottumwa": 25, "Fairfield": 52, "Mt Pleasant": 77, "Bloomfield": 45},
    "Pella": {"Sigourney": 45, "Fairfield": 65, "Albia": 32, "Washington": 75},
    "Ottumwa": {"Mt Pleasant": 49, "Sigourney": 30, "Washington": 55, "Iowa City": 83},
    "Grinnell": {"Coralville": 63, "Cedar Rapids": 74, "Sigourney": 55, "Tama": 25},
    "Marshalltown": {"Cedar Falls": 55, "Cedar Rapids": 73, "Independence": 80, "Grinnell": 31},
    "Newton": {"Sigourney": 68, "Oskaloosa": 45, "Pella": 27, "Iowa City": 85},
    "Chariton": {"Knoxville": 26, "Ottumwa": 49, "Fairfield": 74, "Bloomfield": 64},
    "Mason City": {"Charles City": 30, "Waverly": 61, "Waterloo": 81, "New Hampton": 49},
    "Charles City": {"Oelwein": 62, "Cresco": 49, "Independence": 77, "Waverly": 31},
    "Osage": {"Cresco": 42, "Decorah": 56, "Oelwein": 83, "Cedar Falls": 66},
    "Cedar Falls": {"Independence": 34, "Manchester": 56, "Monticello": 77, "Cedar Rapids": 62},
    "Waterloo": {"Monticello": 69, "Oelwein": 35, "Manchester": 49, "Coralville": 77},
    "Tama": {"Coralville": 70, "Cedar Rapids": 48, "Sigourney": 64, "Marengo": 35},
    "Waverly": {"West Union": 49, "New Hampton": 33, "Decorah": 69, "Dyersville": 85},
    "Hampton": {"Charles City": 50, "Independence": 83, "New Hampton": 66, "Parkersburg": 33},
    "Centerville": {"Fairfield": 67, "Bloomfield": 26, "Ottumwa": 43, "Keosauqua": 52},
    "Albia": {"Keosauqua": 64, "Fairfield": 48, "Washington": 78, "Ottumwa": 23},
    "Fairfield": {"Mt Pleasant": 23, "Washington": 30, "Fort Madison": 59, "Burlington": 50},
    "Bloomfield": {"Mt Pleasant": 61, "Keosauqua": 26, "Fairfield": 39, "Washington": 67},
    "Mt Pleasant": {"Keokuk": 44, "Fort Madison": 34, "Burlington": 29, "Muscatine": 56},
    "Sigourney": {"Muscatine": 71, "Iowa City": 51, "Washington": 29, "Mt Pleasant": 60},
    "Washington": {"Burlington": 61, "Muscatine": 42, "Davenport": 72, "Mt Pleasant": 30},
    "Iowa City": {"Davenport": 57, "Dyersville": 74, "Muscatine": 36, "Monticello": 49},
    "Cedar Rapids": {"Monticello": 38, "Maquoketa": 59, "Dyersville": 64, "Anamosa": 26},
    "Independence": {"Dyersville": 41, "Dubuque": 66, "Anamosa": 53, "Guttenberg": 70},
    "New Hampton": {"Decorah": 38, "West Union": 30, "Oelwein": 47, "Guttenberg": 78},
    "Oelwein": {"Guttenberg": 51, "Anamosa": 68, "Manchester": 36, "Cedar Rapids": 54},
    "Cresco": {"West Union": 39, "Lansing": 56, "Decorah": 20, "Oelwein": 60},
    "Decorah": {"Lansing": 36, "Manchester": 77, "Dyersville": 82, "Elkader": 46},
    "Manchester": {"Dubuque": 45, "Maquoketa": 66, "Anamosa": 33, "Guttenberg": 39},
    "Monticello": {"Dubuque": 37, "Clinton": 72, "Maquoketa": 35, "Davenport": 75},
    "Marengo": {"Anamosa": 61, "Iowa City": 30, "Mt Pleasant": 81, "Independence": 56},
    "Dyersville": {"Dubuque": 27, "Bellevue": 47, "Maquoketa": 50, "Clinton": 82},
    "West Union": {"Lansing": 52, "Guttenberg": 45, "Manchester": 49, "Dyersville": 62},
    "Parkersburg": {"Independence": 54, "Oelwein": 68, "Cedar Rapids": 82, "Waterloo": 27},
    "Keosauqua": {"Mt Pleasant": 36, "Burlington": 57, "Fort Madison": 41, "Keokuk": 47},
    "Anamosa": {"Maquoketa": 35, "Dubuque": 48, "Bellevue": 56, "Dyersville": 33},
    "Maquoketa": {"Bellevue": 21, "Dubuque": 32, "Clinton": 36, "Davenport": 40},
    "Elkader": {"Dubuque": 57, "Guttenberg": 21, "Lansing": 48, "Bellevue": 85},
    "Coralville": {"Davenport": 60, "Dyersville": 77, "Muscatine": 44, "Monticello": 52}
}

ALL_NON_START_TOWNS = [t for t in TOWN_COORDS.keys() if t not in START_TOWNS]

POWER_CARDS = [
    {"name": "Porkchop Power", "reason": "Fueled up by legendary festival food!", "effect_text": "Expand 10 miles to the mileage range in both directions."},
    {"name": "Headwind", "reason": "Fighting a fierce crosswind across open plains!", "effect_text": "Subtract 10 miles to the mileage range in both directions."},
    {"name": "Pie Power", "reason": "Sugar rush from homemade church pie!", "effect_text": "Add 15 miles to the mileage top range."},
    {"name": "Road Closure", "reason": "Unexpected road construction blocks the highway!", "effect_text": "Roll a die: Even = Stay | Odd = Go back one town."},
    {"name": "Downhill", "reason": "Cruising down long rolling Iowa hills!", "effect_text": "Subtract 10 miles to the range on the low end."},
    {"name": "Hangover", "reason": "Late night lingering at the beer tent!", "effect_text": "Subtract 20 miles to the range on the high end."},
    {"name": "100 Degree Day", "reason": "Sweltering Iowa summer heat slows your pace!", "effect_text": "Lower the top range number by 15 miles."},
    {"name": "Fire Station Fundraiser", "reason": "Community pancake breakfast boosts early momentum!", "effect_text": "Lower the bottom range number by 15 miles."},
    {"name": "Casey's Pizza Power", "reason": "Starting the day off right.", "effect_text": "Expand 5 miles to the mileage range in both directions."}
]

ABILITY_DESCRIPTIONS = {
    "Beekman's Energy Boost": "Add 20 miles to top & bottom ranges (-5 pts score penalty).",
    "Thunderstorm": "Multiplayer only: Push opponent back 1 town (No score penalty).",
    "Slip & Slide Boost": "Remove all mileage limits for this turn (-10 pts score penalty)."
}


def get_town_connections(town_name):
    """Return (feeds_in_list, feeds_out_list) for 1-stop direct RAGBRAI_MAP links."""
    feeds_in = [
        (src, destinations[town_name])
        for src, destinations in RAGBRAI_MAP.items()
        if town_name in destinations
    ]
    feeds_out = list(RAGBRAI_MAP.get(town_name, {}).items())
    return feeds_in, feeds_out


def _now_central():
    return datetime.now(CENTRAL_TZ)


def _time_until_next_ragbraile(now_dt=None):
    """Return formatted 'H:MM' remaining until next midnight in Central Time."""
    if now_dt is None:
        now_dt = _now_central()
    elif now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=CENTRAL_TZ)
    else:
        now_dt = now_dt.astimezone(CENTRAL_TZ)

    next_midnight = (now_dt + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    remaining_secs = round((next_midnight - now_dt).total_seconds())
    total_minutes = round(remaining_secs / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}:{minutes:02d}"


def _get_valid_saved_ragbraile(profile, today_day_num):
    """Return saved RAGBRAILE only if it belongs to today's puzzle day; otherwise clear stale one."""
    if not profile:
        return None
    saved = profile.get("active_ragbraile")
    if not saved:
        return None
    if saved.get("day_of_year") != today_day_num:
        profile["active_ragbraile"] = None
        if st.session_state.get("current_username"):
            save_user_profile(st.session_state.current_username, profile)
        return None
    return saved


def _is_ragbraile_session_active():
    today_day_num = _now_central().timetuple().tm_yday
    if st.session_state.get("is_ragbraile") and st.session_state.get("phase") in (
        "playing", "select_starts", "select_start_single"
    ):
        return True
    active_saved = _get_valid_saved_ragbraile(st.session_state.get("user_profile"), today_day_num)
    return bool(active_saved)


def _snapshot_active_ragbraile():
    """Persist current in-progress RAGBRAILE state to profile & session without altering lifetime stats."""
    if not st.session_state.get("is_ragbraile") or not st.session_state.get("players"):
        return
    p0 = st.session_state.players[0]
    snapshot = {
        "saved_at": _now_central().strftime("%Y-%m-%d %H:%M"),
        "day_of_year": st.session_state.get("ragbraile_day_of_year", _now_central().timetuple().tm_yday),
        "ragbraile_pair": list(st.session_state.get("ragbraile_pair", ())),
        "dice_mode": st.session_state.get("dice_mode", "Virtual Dice"),
        "phase": st.session_state.get("phase", "playing"),
        "turn_state": st.session_state.get("turn_state", "roll"),
        "r1": st.session_state.get("r1", 0),
        "r2": st.session_state.get("r2", 0),
        "current_card": st.session_state.get("current_card"),
        "base_low": st.session_state.get("base_low", 0),
        "base_high": st.session_state.get("base_high", 0),
        "mod_low": st.session_state.get("mod_low", 0),
        "mod_high": st.session_state.get("mod_high", 0),
        "road_result_msg": st.session_state.get("road_result_msg"),
        "map_penalty_pts": 15 if st.session_state.get("ragbraile_map_penalty_used") else 0,
        "player": {
            "name": p0.get("name", st.session_state.current_username),
            "town": p0.get("town"),
            "history": list(p0.get("history", [])),
            "abilities": dict(p0.get("abilities", {})),
            "total_turns_taken": p0.get("total_turns_taken", 0),
            "ability_penalty_pts": p0.get("ability_penalty_pts", 0),
            "bonus_range_next_turn": p0.get("bonus_range_next_turn", 0),
            "start_choice": p0.get("start_choice", START_TOWNS[0]),
            "reset_reason": p0.get("reset_reason"),
            "base_mileage_tally": p0.get("base_mileage_tally", 0),
            "day_mileage_history": list(p0.get("day_mileage_history", []))
        }
    }
    st.session_state.user_profile["active_ragbraile"] = snapshot
    save_user_profile(st.session_state.current_username, st.session_state.user_profile)


def _resume_ragbraile_from_snapshot(snap):
    p_snap = snap.get("player", {})
    username = st.session_state.current_username
    st.session_state.dice_mode = snap.get("dice_mode", "Virtual Dice")
    st.session_state.challenge_town_mode = False
    st.session_state.challenge_mileage_mode = False
    st.session_state.is_ragbraile = True
    st.session_state.ragbraile_day_of_year = snap.get("day_of_year", _now_central().timetuple().tm_yday)
    st.session_state.ragbraile_pair = tuple(snap.get("ragbraile_pair", ()))
    st.session_state.ragbraile_map_penalty_used = bool(snap.get("map_penalty_pts", 0) >= 15)
    st.session_state.current_idx = 0
    st.session_state.players = [{
        "name": p_snap.get("name", username),
        "town": p_snap.get("town"),
        "history": list(p_snap.get("history", [])),
        "abilities": dict(p_snap.get("abilities", {"Beekman's Energy Boost": True, "Thunderstorm": True, "Slip & Slide Boost": True})),
        "total_turns_taken": p_snap.get("total_turns_taken", 0),
        "ability_penalty_pts": p_snap.get("ability_penalty_pts", 0),
        "bonus_range_next_turn": p_snap.get("bonus_range_next_turn", 0),
        "start_choice": p_snap.get("start_choice", START_TOWNS[0]),
        "reset_reason": p_snap.get("reset_reason"),
        "base_mileage_tally": p_snap.get("base_mileage_tally", 0),
        "day_mileage_history": list(p_snap.get("day_mileage_history", [])),
        "target_town": None,
        "target_mileage": None
    }]
    st.session_state.turn_state = snap.get("turn_state", "roll")
    st.session_state.r1 = snap.get("r1", 0)
    st.session_state.r2 = snap.get("r2", 0)
    st.session_state.current_card = snap.get("current_card")
    st.session_state.base_low = snap.get("base_low", 0)
    st.session_state.base_high = snap.get("base_high", 0)
    st.session_state.mod_low = snap.get("mod_low", 0)
    st.session_state.mod_high = snap.get("mod_high", 0)
    st.session_state.road_result_msg = snap.get("road_result_msg")
    st.session_state.phase = snap.get("phase", "playing")


def _apply_ragbraile_map_penalty_if_needed():
    if _is_ragbraile_session_active():
        st.session_state.ragbraile_map_penalty_used = True
        if st.session_state.get("is_ragbraile") and st.session_state.get("players"):
            _snapshot_active_ragbraile()
        elif st.session_state.get("user_profile", {}).get("active_ragbraile"):
            st.session_state.user_profile["active_ragbraile"]["map_penalty_pts"] = 15
            save_user_profile(st.session_state.current_username, st.session_state.user_profile)


def compute_ragbraile_score(player, map_penalty_used):
    map_pen = 15 if map_penalty_used else 0
    raw = 107 - player.get("total_turns_taken", 0) - player.get("ability_penalty_pts", 0) - map_pen
    return max(0, min(100, raw))


def _get_ragbraile_day_result(profile, day_num):
    if not profile:
        return None
    results_map = profile.get("ragbraile_results") or {}
    saved = results_map.get(str(day_num)) or results_map.get(day_num)
    if saved and saved.get("history"):
        return saved

    pair_fallback = list(RAGBRAILE_PAIRS[(day_num - 1) % len(RAGBRAILE_PAIRS)])
    for entry in reversed(profile.get("recent_routes", [])):
        if f"RAGBRAILE (Day {day_num})" in entry.get("mode", "") and entry.get("history"):
            score_match = re.search(r'Score:\s*(\d+)', entry.get("extra", ""))
            parsed_score = int(score_match.group(1)) if score_match else 100
            return {
                "day_of_year": day_num,
                "ragbraile_pair": pair_fallback,
                "player_name": profile.get("display_name") or st.session_state.get("current_username", "Player"),
                "history": list(entry["history"]),
                "miles": entry.get("miles", 0),
                "score": parsed_score,
                "total_turns_taken": 7,
                "ability_penalty_pts": 0,
                "map_penalty_pts": 0,
            }
    return None


def _open_ragbraile_day_results(day_num):
    res = _get_ragbraile_day_result(st.session_state.get("user_profile", {}), day_num)
    if not res:
        return False
    map_pen = res.get("map_penalty_pts", 0)
    st.session_state.is_ragbraile = True
    st.session_state.ragbraile_day_of_year = day_num
    st.session_state.ragbraile_pair = tuple(res.get("ragbraile_pair") or RAGBRAILE_PAIRS[(day_num - 1) % len(RAGBRAILE_PAIRS)])
    st.session_state.ragbraile_map_penalty_used = bool(map_pen >= 15)
    st.session_state.celebrate_win = False
    st.session_state.viewing_saved_ragbraile_result = {
        "score": res.get("score", 100),
        "miles": res.get("miles", 0),
        "map_penalty_pts": map_pen,
    }
    st.session_state.winner = {
        "name": res.get("player_name") or st.session_state.current_username,
        "history": list(res.get("history", [])),
        "total_turns_taken": res.get("total_turns_taken", 7),
        "ability_penalty_pts": res.get("ability_penalty_pts", 0),
        "base_mileage_tally": res.get("miles", 0),
    }
    push_phase("game_over")
    return True


def push_phase(target_phase):
    current = st.session_state.get("phase")
    if target_phase == "view_full_map":
        _apply_ragbraile_map_penalty_if_needed()
    if current and current not in ("view_stats", "view_full_map"):
        st.session_state.nav_stack.append(current)
    elif current and current != target_phase:
        if not st.session_state.nav_stack or st.session_state.nav_stack[-1] != current:
            st.session_state.nav_stack.append(current)
    st.session_state.phase = target_phase


def pop_phase(fallback="setup"):
    while st.session_state.nav_stack and st.session_state.nav_stack[-1] == st.session_state.phase:
        st.session_state.nav_stack.pop()
    if st.session_state.nav_stack:
        st.session_state.phase = st.session_state.nav_stack.pop()
    else:
        st.session_state.phase = fallback


# --- BUILD 366 RAGBRAILE PAIRS CACHE VIA BFS (<= 7 HOPS) ---
@st.cache_data
def get_ragbraile_pairs():
    hops = {}
    for start_t in TOWN_COORDS.keys():
        visited = {start_t: 0}
        queue = [start_t]
        while queue:
            curr = queue.pop(0)
            curr_dist = visited[curr]
            if curr_dist < 7:
                for neighbor in RAGBRAI_MAP.get(curr, {}).keys():
                    if neighbor not in visited:
                        visited[neighbor] = curr_dist + 1
                        queue.append(neighbor)
        hops[start_t] = visited

    town_list = sorted(list(TOWN_COORDS.keys()))
    valid_pairs = []
    for a in town_list:
        for b, h in hops[a].items():
            if a != b and 1 <= h <= 7:
                valid_pairs.append((a, b))
                
    random.seed(2026)
    random.shuffle(valid_pairs)
    
    selected_pairs = []
    idx = 0
    while len(selected_pairs) < 366:
        selected_pairs.append(valid_pairs[idx % len(valid_pairs)])
        idx += 1
    return selected_pairs

RAGBRAILE_PAIRS = get_ragbraile_pairs()

def roll_2d6():
    return random.randint(1, 6) + random.randint(1, 6)

def calculate_player_mileage(player):
    return player['base_mileage_tally']

# --- INITIALIZE SESSION STATE ---
if "current_username" not in st.session_state:
    st.session_state.current_username = ""

if "user_profile" not in st.session_state:
    st.session_state.user_profile = {}

if "nav_stack" not in st.session_state:
    st.session_state.nav_stack = []

if "ragbraile_map_penalty_used" not in st.session_state:
    st.session_state.ragbraile_map_penalty_used = False

if "ragbraile_day_of_year" not in st.session_state:
    st.session_state.ragbraile_day_of_year = _now_central().timetuple().tm_yday

if "celebrate_win" not in st.session_state:
    st.session_state.celebrate_win = False

if "viewing_saved_ragbraile_result" not in st.session_state:
    st.session_state.viewing_saved_ragbraile_result = None

if "phase" not in st.session_state:
    st.session_state.phase = "login"
    st.session_state.players = []
    st.session_state.current_idx = 0
    st.session_state.dice_mode = "Virtual Dice"
    st.session_state.challenge_town_mode = False
    st.session_state.challenge_mileage_mode = False
    st.session_state.is_ragbraile = False
    st.session_state.ragbraile_pair = ()
    st.session_state.turn_state = "roll"
    st.session_state.r1 = 0
    st.session_state.r2 = 0
    st.session_state.current_card = None
    st.session_state.base_low = 0
    st.session_state.base_high = 0
    st.session_state.mod_low = 0
    st.session_state.mod_high = 0
    st.session_state.road_result_msg = None
    st.session_state.winner = None

# --- SIDEBAR NAVIGATION & LOG BOOK CONTROLS ---
with st.sidebar:
    st.header("⚙️ Game Menu")
    
    if st.session_state.phase != "login":
        st.write(f"👤 **Player:** `{st.session_state.current_username}`")
        
        if st.session_state.phase != "view_stats":
            if st.button("📊 View My Stats"):
                push_phase("view_stats")
                st.rerun()

        if st.session_state.phase != "view_full_map":
            if st.button("🗺️ View Full Town Map"):
                push_phase("view_full_map")
                st.rerun()

        if st.session_state.phase in ["playing", "select_start_single"]:
            if st.button("🔄 Restart Current Route"):
                current_p = st.session_state.players[st.session_state.current_idx]
                current_p['reset_reason'] = f"Player {current_p['name']} requested a route reset."
                current_p['start_choice'] = START_TOWNS[0]
                st.session_state.phase = "select_start_single"
                if st.session_state.get("is_ragbraile"):
                    _snapshot_active_ragbraile()
                st.rerun()
                
            if st.button("🏠 Quit to Home Menu"):
                if st.session_state.get("is_ragbraile"):
                    _snapshot_active_ragbraile()
                st.session_state.nav_stack = []
                st.session_state.phase = "setup"
                st.rerun()

        if st.button("🚪 Switch User / Logout"):
            if st.session_state.get("is_ragbraile"):
                _snapshot_active_ragbraile()
            st.session_state.current_username = ""
            st.session_state.user_profile = {}
            st.session_state.is_ragbraile = False
            st.session_state.ragbraile_map_penalty_used = False
            st.session_state.viewing_saved_ragbraile_result = None
            st.session_state.nav_stack = []
            st.session_state.phase = "login"
            st.rerun()

        st.markdown("---")
        st.header("📖 Town Log Book")
        user_towns_log = set(st.session_state.user_profile.get("completed_towns", []))
        completed_count = len(user_towns_log)
        st.write(f"**Lifetime Coverage:** {completed_count} / 99 Towns")
        
        with st.expander("View 99 Towns Checklist", expanded=False):
            all_sorted_towns = sorted(list(TOWN_COORDS.keys()))
            for t in all_sorted_towns:
                if t in user_towns_log:
                    st.write(f"✅ **{t}**")
                else:
                    st.write(f"⚪ {t}")

# --- MAP GENERATORS ---
def get_map(players):
    m = folium.Map(
        location=[42.0111, -93.2105], 
        zoom_start=7, 
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles © Esri'
    )
    palette = ["blue", "green", "purple", "orange", "darkred", "cadetblue"]
    for i, p in enumerate(players):
        history = p['history']
        if not history:
            continue
        p_color = palette[i % len(palette)]
        coords = [TOWN_COORDS[t] for t in history if t in TOWN_COORDS]
        if len(coords) > 1:
            folium.PolyLine(coords, color=p_color, weight=4, opacity=0.8).add_to(m)
        for idx, town in enumerate(history):
            if town in TOWN_COORDS:
                lat, lon = TOWN_COORDS[town]
                folium.Marker(
                    [lat, lon],
                    popup=f"<b>{p['name']}</b><br>{town} (Day {idx})",
                    icon=folium.Icon(color=p_color, icon="bicycle", prefix="fa")
                ).add_to(m)
    return m

def get_all_towns_map():
    m = folium.Map(
        location=[42.0111, -93.2105], 
        zoom_start=7, 
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles © Esri'
    )
    for town, coords in TOWN_COORDS.items():
        if town in START_TOWNS:
            icon_color, icon_name = "green", "play"
            category = "Start Town"
        elif town in FINISH_TOWNS:
            icon_color, icon_name = "flag", "flag"
            category = "Finish Town"
        else:
            icon_color, icon_name = "blue", "info-sign"
            category = "Pass-Through Town"

        feeds_in, feeds_out = get_town_connections(town)
        in_html = "<br>".join([f"• {src} ({mi} mi)" for src, mi in feeds_in]) if feeds_in else "• None"
        out_html = "<br>".join([f"• {dst} ({mi} mi)" for dst, mi in feeds_out]) if feeds_out else "• None (Finish Town)"

        popup_html = (
            f"<div style='min-width: 190px;'>"
            f"<b>{town}</b> ({category})<br><br>"
            f"<b>⬅️ Feeds In (1 stop):</b><br>{in_html}<br><br>"
            f"<b>➡️ Feeds Out (1 stop):</b><br>{out_html}"
            f"</div>"
        )
            
        folium.Marker(
            coords,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=town,
            icon=folium.Icon(color=icon_color, icon=icon_name)
        ).add_to(m)

        folium.Marker(
            coords,
            icon=DivIcon(
                icon_size=(150, 36),
                icon_anchor=(75, -12),
                html=f'<div style="font-size: 8pt; font-weight: bold; color: #333333; text-shadow: 1px 1px 0px #ffffff, -1px -1px 0px #ffffff, 1px -1px 0px #ffffff, -1px 1px 0px #ffffff; text-align: center;">{town}</div>'
            )
        ).add_to(m)
    return m

# --- APP UI ---
st.title("RAGBRAI: The Game")

# ================= LOGIN PHASE =================
if st.session_state.phase == "login":
    st.subheader("👤 Player Sign-In")
    st.write("Enter your unique username below. If your username exists, your lifetime stats and Town Log Book will load automatically; otherwise, a brand-new profile will be created for you.")
    
    with st.form("login_form"):
        typed_user = st.text_input("Enter Username", placeholder="e.g., biker26")
        submitted = st.form_submit_button("Start / Load Profile", type="primary")
        
        if submitted:
            cleaned = typed_user.strip()
            if cleaned:
                prof, existed = load_user_profile(cleaned)
                st.session_state.current_username = cleaned
                st.session_state.user_profile = prof
                today_num = _now_central().timetuple().tm_yday
                saved_rb = _get_valid_saved_ragbraile(prof, today_num)
                st.session_state.ragbraile_map_penalty_used = bool(saved_rb and saved_rb.get("map_penalty_pts", 0) >= 15)
                st.session_state.login_notice = (
                    f"Welcome back, **{cleaned}**! Your saved profile has been loaded."
                    if existed else
                    f"Created a brand-new profile for **{cleaned}**!"
                )
                st.session_state.nav_stack = []
                st.session_state.phase = "setup"
                st.rerun()
            else:
                st.warning("Please enter a valid username to continue.")

# ================= STATS VIEW =================
elif st.session_state.phase == "view_stats":
    st.subheader(f"📊 Career Statistics: {st.session_state.current_username}")
    
    if st.button("🔙 Back"):
        pop_phase("setup")
        st.rerun()

    prof = st.session_state.user_profile
    recent_routes = prof.get("recent_routes", [])
    
    route_std_scores = [
        int(re.search(r'Score:\s*(\d+)', r.get('extra', '')).group(1))
        for r in recent_routes
        if "RAGBRAILE" not in r.get("mode", "") and "Score:" in r.get('extra', '')
    ]
    prof_best_std = prof.get("best_score", 0)
    prof_sum_std = prof.get("total_score_sum", 0)
    prof_wins_std = prof.get("standard_wins", 0)

    best_std_score = max([prof_best_std] + route_std_scores) if (prof_best_std or route_std_scores) else 0
    if route_std_scores and len(route_std_scores) >= prof_wins_std:
        avg_std_score = round(sum(route_std_scores) / len(route_std_scores), 1)
    elif prof_wins_std > 0 and prof_sum_std > 0:
        avg_std_score = round(prof_sum_std / prof_wins_std, 1)
    elif route_std_scores:
        avg_std_score = round(sum(route_std_scores) / len(route_std_scores), 1)
    else:
        avg_std_score = 0

    route_rb_scores = [
        int(re.search(r'Score:\s*(\d+)', r.get('extra', '')).group(1))
        for r in recent_routes
        if "RAGBRAILE" in r.get("mode", "") and "Score:" in r.get('extra', '')
    ]
    prof_best_rb = prof.get("best_ragbraile_score", 0)
    prof_sum_rb = prof.get("ragbraile_score_sum", 0)
    prof_count_rb = prof.get("ragbraile_completions_count", 0)

    best_rb_score = max([prof_best_rb] + route_rb_scores) if (prof_best_rb or route_rb_scores) else 0
    if route_rb_scores and len(route_rb_scores) >= prof_count_rb:
        avg_rb_score = round(sum(route_rb_scores) / len(route_rb_scores), 1)
    elif prof_count_rb > 0 and prof_sum_rb > 0:
        avg_rb_score = round(prof_sum_rb / prof_count_rb, 1)
    elif route_rb_scores:
        avg_rb_score = round(sum(route_rb_scores) / len(route_rb_scores), 1)
    else:
        avg_rb_score = 0

    current_streak = prof.get("current_streak", 0)
    solved_days = prof.get("ragbraile_days_solved", [])
    today_day_num = _now_central().timetuple().tm_yday
    today_str = _now_central().strftime("%Y-%m-%d")
    
    if today_day_num in solved_days and current_streak == 0:
        current_streak = 1
        prof["current_streak"] = 1
        prof["last_solved_date"] = today_str
        save_user_profile(st.session_state.current_username, prof)

    route_miles_list = [r.get('miles', 0) for r in recent_routes if 'miles' in r]
    games_finished_count = prof.get("games_finished", 0)
    total_miles_ridden = prof.get("total_miles_ridden", 0)
    
    avg_mileage = round(total_miles_ridden / games_finished_count, 1) if games_finished_count > 0 else 0
    longest_route = max(route_miles_list) if route_miles_list else 0
    shortest_route = min(route_miles_list) if route_miles_list else 0

    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    r1_c1.metric("Total Games Finished", games_finished_count)
    r1_c2.metric("Towns Visited", f"{len(prof.get('completed_towns', []))} / 99")
    r1_c3.metric("Best Standard Score", f"{best_std_score} / 100")
    r1_c4.metric("Average Standard Score", f"{avg_std_score} / 100")

    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
    r2_c1.metric("Total RAGBRAILEs Completed", len(solved_days))
    r2_c2.metric("RAGBRAILE Daily Streak", f"{current_streak} days")
    r2_c3.metric("Best RAGBRAILE Score", f"{best_rb_score} / 100")
    r2_c4.metric("Average RAGBRAILE Score", f"{avg_rb_score} / 100")

    r3_c1, r3_c2, r3_c3, r3_c4 = st.columns(4)
    r3_c1.metric("Lifetime Miles Ridden", f"{total_miles_ridden:,} mi")
    r3_c2.metric("Average Mileage", f"{avg_mileage:,} mi")
    r3_c3.metric("Shortest Route", f"{shortest_route:,} mi")
    r3_c4.metric("Longest Route", f"{longest_route:,} mi")

    town_visit_counts = Counter()
    for r in recent_routes:
        route_towns = r.get('history', [])
        if route_towns:
            for t in route_towns:
                town_visit_counts[t] += 1
        else:
            start_t = r.get('start')
            end_t = r.get('end')
            if start_t:
                town_visit_counts[start_t] += 1
            if end_t:
                town_visit_counts[end_t] += 1
                
    if not town_visit_counts and prof.get("completed_towns"):
        for t in prof.get("completed_towns"):
            town_visit_counts[t] += 1

    top_5_towns = town_visit_counts.most_common(5)
    
    if top_5_towns:
        st.markdown("#### 🌟 Top 5 Most Visited Towns")
        top_5_str = ", ".join([f"{town} ({count})" for town, count in top_5_towns])
        st.write(top_5_str)

    if recent_routes:
        st.markdown("#### 🚴 Recent Completed Routes")
        for r in reversed(recent_routes[-10:]):
            st.markdown(f"- **{r['date']}** | *{r['mode']}* | **{r['start']} ➔ {r['end']}** ({r['miles']} mi){r.get('extra', '')}")
    else:
        st.info("No completed routes recorded yet. Finish a 7-day ride across Iowa to log your first entry!")

# ================= FULL MAP VIEW =================
elif st.session_state.phase == "view_full_map":
    st.subheader("🗺️ Towns Reference Map")
    st.write("🟢 **Green Markers** = Start Towns | 🔴 **Red Flag Markers** = Finish Towns | 🔵 **Blue Markers** = Interior Towns")
    st.caption("Click any town marker on the map to inspect which towns feed directly into it (1 stop away) and which route options feed directly out of it (1 stop away).")
    
    if st.button("🔙 Back"):
        pop_phase("setup")
        st.rerun()

    col_map_full, col_town_info = st.columns([1.45, 1])

    with col_map_full:
        full_m = get_all_towns_map()
        map_data = st_folium(full_m, width=850, height=600, returned_objects=["last_object_clicked_tooltip", "last_object_clicked"])

    clicked_town = None
    if map_data:
        tooltip_val = map_data.get("last_object_clicked_tooltip")
        if tooltip_val in TOWN_COORDS:
            clicked_town = tooltip_val
        elif map_data.get("last_object_clicked"):
            c_lat = map_data["last_object_clicked"].get("lat")
            c_lng = map_data["last_object_clicked"].get("lng")
            if c_lat is not None and c_lng is not None:
                best_t = min(
                    TOWN_COORDS.keys(),
                    key=lambda t: (TOWN_COORDS[t][0] - c_lat) ** 2 + (TOWN_COORDS[t][1] - c_lng) ** 2
                )
                if ((TOWN_COORDS[best_t][0] - c_lat) ** 2 + (TOWN_COORDS[best_t][1] - c_lng) ** 2) < 0.01:
                    clicked_town = best_t

    with col_town_info:
        st.markdown("### 🏙️ Town Route Connections")
        if clicked_town:
            feeds_in, feeds_out = get_town_connections(clicked_town)
            t_stat = TOWN_HISTORY_DATA.get(clicked_town, {"count": 0, "last": "N/A"})
            st.success(f"**Selected Town:** {clicked_town} *(Hosted {t_stat['count']} times, last in {t_stat['last']})*")

            st.markdown("#### ⬅️ Feeds Into This Town (1 Stop Away)")
            if feeds_in:
                for src, mi in feeds_in:
                    st.markdown(f"- **{src}** ➔ {clicked_town} *({mi} mi)*")
            else:
                st.write("No towns feed directly into this town.")

            st.markdown("#### ➡️ Feeds Out From This Town (1 Stop Away)")
            if feeds_out:
                for dst, mi in feeds_out:
                    st.markdown(f"- {clicked_town} ➔ **{dst}** *({mi} mi)*")
            else:
                st.write("No outgoing route options from this town (Mississippi finish town).")
        else:
            st.info("Click any town marker on the map to see which towns feed into it and which towns it feeds out to.")

# ================= SETUP PHASE =================
elif st.session_state.phase == "setup":
    if "login_notice" in st.session_state and st.session_state.login_notice:
        st.success(st.session_state.login_notice)
        st.session_state.login_notice = None

    with st.expander("📖 **Game Instructions (Click to expand/collapse)**", expanded=False):
        st.markdown("""
        ### 🚴 Introduction
        Welcome to my RAGBRAI game! I've completed 4 full RAGBRAIs with my dad as of 2026 (as well as a handful of partial days growing up). During my 3rd RAGBRAI, our group did daily BINGO cards and one of the items was to come up with an idea for a RAGBRAI game. Since then, the concept of a RAGBRAI game has never really left my mind and you're looking at the result. This is purely for fun and not at all owned by RAGBRAI. I included 99 Iowa towns (for now) and a few popular vendors and keep in mind that mileages are estimates. Please enjoy the game and let me know any feedback you have! Hope to see you out on the road next year for RAGBRAI 54 but in the meantime, navigate your virtual bicycle across Iowa from the Missouri River all the way to the mighty Mississippi! It's RAGBRAI: The Game.

        ---

        ### 🎯 How to Play
        * **Number of Players:** This game can be played solo or with any number of friends on the same machine. Select the number of players below.
        * **Starting the Game:** After selecting your game settings, each player will be prompted to choose 1 of 10 total starting towns on the Western edge of Iowa.
        * **Gameplay:**
          * **Rolling Dice:** Players will take turns rolling two sets of real or virtual six-sided die (select your option below). Your two sets of die roll totals (ranging 2-12) represent your base daily riding mileage range when multiplied by 10 (rolling 6 and 8 results in a base range of 60-80 miles).
          * **Drawing Power Card:** Upon getting your base daily mileage range from the dice rolls, you will then draw a virtual power card. These power cards are randomly selected and will affect your base mileage range by either expanding or shrinking it. One of the possible cards is a road closing, forcing you to go back to your previous town unless you roll an even number on a one-die roll.
          * **Choosing Next Town:** With the final adjusted mileage range available, you will see 4 town options with varying distances that you can ride to from the town that you're currently in. Only towns within the mileage range will be available for you to select. If you have no options, you'll be forced back to the previous town you were in for your next turn. If you do have towns to choose from, you may choose to stay in the town you're currently in if you believe that helps your game strategy.
        * **Main Objective:** Reach any Mississippi River finish town in exactly **7 Days** (8 total stops including your start town near the Missouri River). This requires players to strategically consider where they're choosing to ride to each day, ensuring that their journey is properly spaced out across Iowa.

        ---

        ### 🏆 Ways to Play
        This game is designed to have many different game modes, all available to allow you to customize your RAGBRAI game experience. There's no right or wrong way to play – kind of like there's no right or wrong way to RAGBRAI.
        * **RAGBRAILE:** Like Wordle, but make it RAGBRAI. Come back daily for a new challenge - everyone will receive the same 2 towns and your goal is to complete a full route while traversing through both. Scoring: Maximum 100 points - utilizing special abilities (specified below) deducts points, as does every extra turns more than 7 (-1 for each), and utilizing the Full Route Map (-15 utilizing it 1+ times). This is a solo-only game mode.
        * **Race to the Finish:** While RAGBRAI may not be a race, multiplayer mode in this game rewards the victory to the player who can reach an end town (in exactly 7 days) first.
        * **Perfect Score:** Finish your route in exactly 7 turns with no hiccups and not utilizing any special abilities (listed below) to score a perfect 100 points. Any extra turns required to get to the end town result in losing points. Selecting none (-3), one (-2), or both (-1) of the challenge mode options listed below dictate how many points you lose for each additional turn to reach the Mississippi. Additionally, using special abilities will decrease your score, as specified below. This mode is best enjoyed solo but every non-RAGBRAILE game winning route will receive a score.
        * **Total Tourist:** Utilize your **Town Log Book** on the sidebar to track how many and which of the 99 total towns in the game that you've visited across all your routes on your profile. Only the 8 towns that are involved in a complete game-winning route are added to your log book. 
        * **Challenge Mode:** If the normal game isn't challenging enough, select one or both challenge mode options to add to your standard game (available in both solo and multiplayer games):
          * **Mandatory Town:** At the beginning of the game, each player receives a different randomly-assigned, non-starting town that they must pass through before reaching the Mississippi River to complete their route.
          * **Target Mileage:** At the beginning of the game, each player receives a different total week-long mileage (between 350–550 miles) that your final route must land within **35 miles** of. Your total weekly mileage consists of your daily totals + a random number between 5 & 10 each day to account for riding inefficiently through towns along the way.

        ---

        ### ⚡ Special Abilities
        Each player starts with 3 one-time-use abilities:
        * **Beekman's Energy Boost:** Expands the mileage range on one turn by 20 miles to both the floor and ceiling of range that the player was given. This ability deducts 5 points from your total game score.
        * **Slip & Slide Boost:** Completely remove your mileage limitations for one turn, allowing you to ride to any of the 4 towns listed from the town you're currently at. This ability deducts 10 points from your total game score.
        * **Thunderstorm (multiplayer only):** Use this ability to knock any opponent back one town to the one they were most recently at. This ability does NOT deduct points from your total game score.
        Multiplayer Effect: Whenever any player uses a special ability, all opponents receive a **5-mile range bonus** on both ends of their mileage range on their next turn.

        ---

        ### ⚙️ In-Game & Sidebar Options
        * **View Stats:** Click the **View My Stats** button on the sidebar to view the lifetime statistics of the username that is signed into the current session.
        * **Full Town Map:** You can click the **View Full Town Map** button on the sidebar at any time to inspect all 99 game towns simultaneously. Use **Back to Game** to resume right where you left off!
        * **Restart Route:** Select the **Restart Current Route** button on the sidebar during your turn to completely restart your route from the Missouri River at the same or new starting town. This doesn't impact the current game settings or any opponent's progress in the game that you're in the middle of. It also remembers any special abilities you've used in that current game.
        * **Quit to Home:** Select **Quit to Home Menu** on the sidebar to quit your current game and bring you back to this home screen. If you want to reset your special abilities for the game you're playing and start from scratch, use this button instead of Restart Route.
        * **Switch User/Logout:** If you want to change the username that is currently logged in, click this button.
        * **Town Log Book:** Utilize your **Town Log Book** on the sidebar to track how many and which of the 99 total towns in the game that you've visited across your persistent profile. Only the 8 towns that are involved in a complete game-winning route are added to your log book. 
        """)

    # --- RAGBRAILE LAUNCH / RESUME / COMPLETED SECTION ---
    today_dt = _now_central()
    day_of_year = today_dt.timetuple().tm_yday
    solved_days = set(st.session_state.user_profile.get("ragbraile_days_solved", []))
    saved_rb = _get_valid_saved_ragbraile(st.session_state.user_profile, day_of_year)
    
    st.markdown("### 🗓️ Daily Challenge Mode")
    if day_of_year in solved_days:
        countdown_str = _time_until_next_ragbraile(today_dt)
        has_result = _get_ragbraile_day_result(st.session_state.user_profile, day_of_year) is not None
        if has_result:
            col_done_msg, col_view_res = st.columns([2.4, 1])
            with col_done_msg:
                st.success(f"✅ You've completed today's RAGBRAILE! Next RAGBRAILE in **{countdown_str}**")
            with col_view_res:
                if st.button("📊 View Today's Results", type="primary", use_container_width=True):
                    if _open_ragbraile_day_results(day_of_year):
                        st.rerun()
        else:
            st.success(f"✅ You've completed today's RAGBRAILE! Next RAGBRAILE in **{countdown_str}**")
    elif saved_rb:
        s_pair = saved_rb.get("ragbraile_pair", RAGBRAILE_PAIRS[day_of_year - 1])
        s_day = saved_rb.get("day_of_year", day_of_year)
        s_hist = saved_rb.get("player", {}).get("history", [])
        s_curr = saved_rb.get("player", {}).get("town") or saved_rb.get("player", {}).get("start_choice", START_TOWNS[0])
        st.info(
            f"💾 **Saved RAGBRAILE In Progress** (Puzzle Day {s_day} • Targets: **{s_pair[0]} & {s_pair[1]}** • "
            f"Current Stop: **{s_curr}**, Day {max(0, len(s_hist) - 1)} • Saved {saved_rb.get('saved_at', 'earlier')})"
        )
        if st.button("▶️ Resume Saved RAGBRAILE", type="primary"):
            _resume_ragbraile_from_snapshot(saved_rb)
            st.rerun()
    else:
        ragbraile_dice_choice = st.selectbox("Select Dice Mode for RAGBRAILE", ["Virtual Dice", "Real-Life Dice"], key="ragbraile_dice_select")
        if st.button(f"Play RAGBRAILE (Today's Puzzle: Day {day_of_year})", type="primary"):
            st.session_state.ragbraile_map_penalty_used = False
            st.session_state.viewing_saved_ragbraile_result = None
            st.session_state.dice_mode = ragbraile_dice_choice
            st.session_state.is_ragbraile = True
            st.session_state.ragbraile_day_of_year = day_of_year
            st.session_state.ragbraile_pair = RAGBRAILE_PAIRS[day_of_year - 1]
            st.session_state.players = [{
                "name": st.session_state.current_username,
                "town": None,
                "history": [],
                "abilities": {"Beekman's Energy Boost": True, "Thunderstorm": True, "Slip & Slide Boost": True},
                "total_turns_taken": 0,
                "ability_penalty_pts": 0,
                "bonus_range_next_turn": 0,
                "start_choice": START_TOWNS[0],
                "reset_reason": None,
                "base_mileage_tally": 0,
                "day_mileage_history": [],
                "target_town": None,
                "target_mileage": None
            }]
            _snapshot_active_ragbraile()
            st.session_state.phase = "select_starts"
            st.rerun()

    st.markdown("---")
    st.subheader("⚙️ Custom Game")
    num_players = st.number_input("Number of Players (1 for Solo)", min_value=1, max_value=6, value=1, step=1)
    st.session_state.dice_mode = st.selectbox("Select Dice Mode", ["Virtual Dice", "Real-Life Dice"], key="custom_dice_select")
    
    st.markdown("#### 🏆 Challenge Mode Options (Select independently or combine)")
    st.session_state.challenge_town_mode = st.checkbox("📍 Mandatory Town", value=False)
    st.session_state.challenge_mileage_mode = st.checkbox("🎯 Required Mileage Range", value=False)
    
    player_names = [st.session_state.current_username]
    for i in range(1, int(num_players)):
        name = st.text_input(f"Player {i+1} Name", value=f"Player {i+1}", key=f"p_name_{i}")
        player_names.append(name)

    if st.button("Proceed to Start Town Selection"):
        st.session_state.is_ragbraile = False
        st.session_state.viewing_saved_ragbraile_result = None
        st.session_state.players = []
        for name in player_names:
            p_data = {
                "name": name,
                "town": None,
                "history": [],
                "abilities": {"Beekman's Energy Boost": True, "Thunderstorm": True, "Slip & Slide Boost": True},
                "total_turns_taken": 0,
                "ability_penalty_pts": 0,
                "bonus_range_next_turn": 0,
                "start_choice": START_TOWNS[0],
                "reset_reason": None,
                "base_mileage_tally": 0,
                "day_mileage_history": [],
                "target_town": random.choice(ALL_NON_START_TOWNS) if st.session_state.challenge_town_mode else None,
                "target_mileage": random.randint(350, 550) if st.session_state.challenge_mileage_mode else None
            }
            st.session_state.players.append(p_data)
        st.session_state.phase = "select_starts"
        st.rerun()

# ================= START TOWN SELECTION (INITIAL) =================
elif st.session_state.phase == "select_starts":
    st.subheader("Select Starting Towns")
    for p in st.session_state.players:
        st.markdown(f"#### 👤 {p['name']}")
        if st.session_state.is_ragbraile:
            t1, t2 = st.session_state.ragbraile_pair
            st.info(f"🗓️ **RAGBRAILE Daily Challenge:** Must visit mandatory towns **{t1}** and **{t2}** within 7 days and finish at the Mississippi!")
        else:
            challenges_txt = []
            if st.session_state.challenge_town_mode:
                challenges_txt.append(f"Mandatory Town: **{p['target_town']}**")
            if st.session_state.challenge_mileage_mode:
                challenges_txt.append(f"Target Mileage: **{p['target_mileage']} ± 35 mi**")
            if challenges_txt:
                st.info(f"🎯 **Challenge Goals:** " + " | ".join(challenges_txt))
        p['start_choice'] = st.selectbox(f"Select Western Start Town for {p['name']}:", START_TOWNS, key=f"start_{p['name']}")

    if st.button("Start Game!"):
        for p in st.session_state.players:
            p['town'] = p['start_choice']
            p['history'] = [p['town']]
            p['base_mileage_tally'] = 0
            p['day_mileage_history'] = []
        st.session_state.phase = "playing"
        st.session_state.turn_state = "roll"
        if st.session_state.is_ragbraile:
            _snapshot_active_ragbraile()
        st.rerun()

# ================= INDIVIDUAL PLAYER START RE-SELECTION =================
elif st.session_state.phase == "select_start_single":
    current_p = st.session_state.players[st.session_state.current_idx]
    st.subheader(f"🔄 Restart Route: {current_p['name']}")
    if current_p['reset_reason']:
        st.warning(current_p['reset_reason'])
    
    if st.session_state.is_ragbraile:
        t1, t2 = st.session_state.ragbraile_pair
        st.info(f"🗓️ **RAGBRAILE Daily Challenge:** **{t1}** & **{t2}**")
    else:
        challenges_txt = []
        if st.session_state.challenge_town_mode:
            challenges_txt.append(f"Mandatory Town: **{current_p['target_town']}**")
        if st.session_state.challenge_mileage_mode:
            challenges_txt.append(f"Target Mileage: **{current_p['target_mileage']} ± 35 mi**")
        if challenges_txt:
            st.info(f"🎯 **Challenge Goals:** " + " | ".join(challenges_txt))

    new_start = st.selectbox(f"Select New Western Start Town for {current_p['name']}:", START_TOWNS, key=f"single_start_{current_p['name']}")
    
    if st.button("Confirm New Start & End Turn"):
        current_p['start_choice'] = new_start
        current_p['town'] = new_start
        current_p['history'] = [current_p['town']]
        current_p['base_mileage_tally'] = 0
        current_p['day_mileage_history'] = []
        current_p['reset_reason'] = None
        
        st.session_state.phase = "playing"
        st.session_state.turn_state = "roll"
        st.session_state.current_idx = (st.session_state.current_idx + 1) % len(st.session_state.players)
        if st.session_state.is_ragbraile:
            _snapshot_active_ragbraile()
        st.rerun()

# ================= PLAYING PHASE =================
elif st.session_state.phase == "playing":
    current_p = st.session_state.players[st.session_state.current_idx]
    current_day = len(current_p['history'])
    is_solo = len(st.session_state.players) == 1

    temp_bonus = current_p['bonus_range_next_turn']

    col_control, col_map = st.columns([1, 1])

    with col_control:
        st.markdown(f"### 👉 {current_p['name']}'s Turn (Day {current_day})")
        
        curr_town = current_p['town']
        town_stat = TOWN_HISTORY_DATA.get(curr_town, {"count": 0, "last": "N/A"})
        st.info(f"📍 **Current Location:** {curr_town} (Hosted {town_stat['count']} times, last in {town_stat['last']})")

        if st.session_state.is_ragbraile:
            t1, t2 = st.session_state.ragbraile_pair
            v1 = "✅" if t1 in current_p['history'] else "❌"
            v2 = "✅" if t2 in current_p['history'] else "❌"
            st.warning(f"🗓️ **RAGBRAILE Mandatory Towns:** {v1} {t1} | {v2} {t2}")
            if st.session_state.ragbraile_map_penalty_used:
                st.caption("⚠️ Full Town Map penalty active (-15 pts max) for this RAGBRAILE run.")
        else:
            challenge_goals_list = []
            if st.session_state.challenge_town_mode:
                challenge_goals_list.append(f"Must visit **{current_p['target_town']}**")
            if st.session_state.challenge_mileage_mode:
                challenge_goals_list.append(f"Target: **{current_p['target_mileage']-35}–{current_p['target_mileage']+35} mi**")
            if challenge_goals_list:
                st.warning(f"🎯 **Challenge Goal:** " + " | ".join(challenge_goals_list))

        if st.session_state.turn_state == "roll":
            if temp_bonus > 0:
                st.success(f"⚡ Opponent Ability Bonus Active! Range expanded by +{temp_bonus} miles in both directions.")

            if st.session_state.dice_mode.startswith("Virtual"):
                if st.button("🎲 Roll Daily Dice"):
                    r1 = roll_2d6()
                    r2 = roll_2d6()
                    st.session_state.r1 = r1
                    st.session_state.r2 = r2
                    
                    low_r = min(r1, r2)
                    high_r = max(r1, r2)
                    st.session_state.base_low = low_r * 10
                    st.session_state.base_high = high_r * 10
                    st.session_state.road_result_msg = None
                    
                    st.session_state.turn_state = "card"
                    if st.session_state.is_ragbraile:
                        _snapshot_active_ragbraile()
                    st.rerun()
            else:
                st.write("Enter your physical dice roll sums (2-12):")
                r1_input = st.number_input("First Dice Pair Sum", 2, 12, 7)
                r2_input = st.number_input("Second Dice Pair Sum", 2, 12, 7)
                if st.button("Submit Real Dice"):
                    st.session_state.r1 = r1_input
                    st.session_state.r2 = r2_input
                    
                    low_r = min(r1_input, r2_input)
                    high_r = max(r1_input, r2_input)
                    st.session_state.base_low = low_r * 10
                    st.session_state.base_high = high_r * 10
                    st.session_state.road_result_msg = None
                    
                    st.session_state.turn_state = "card"
                    if st.session_state.is_ragbraile:
                        _snapshot_active_ragbraile()
                    st.rerun()

        elif st.session_state.turn_state == "card":
            st.write(f"🎲 Dice Rolls: **{st.session_state.r1}** and **{st.session_state.r2}**")
            st.success(f"📊 **Base Daily Range:** {st.session_state.base_low} to {st.session_state.base_high} miles")

            if st.button("🃏 Draw Daily Power Card"):
                card = random.choice(POWER_CARDS)
                st.session_state.current_card = card
                
                ml, mh = st.session_state.base_low, st.session_state.base_high
                if card['name'] == "Porkchop Power":
                    ml = max(0, st.session_state.base_low - 10)
                    mh = st.session_state.base_high + 10
                elif card['name'] == "Headwind":
                    ml = st.session_state.base_low + 10
                    mh = max(ml, st.session_state.base_high - 10)
                elif card['name'] == "Pie Power":
                    mh = st.session_state.base_high + 15
                elif card['name'] == "Downhill":
                    ml = max(0, st.session_state.base_low - 10)
                elif card['name'] == "Hangover":
                    mh = max(ml, st.session_state.base_high - 20)
                elif card['name'] == "100 Degree Day":
                    mh = max(ml, st.session_state.base_high - 15)
                elif card['name'] == "Fire Station Fundraiser":
                    ml = max(0, st.session_state.base_low - 15)
                elif card['name'] == "Casey's Pizza Power":
                    ml = max(0, st.session_state.base_low - 5)
                    mh = st.session_state.base_high + 5

                if temp_bonus > 0:
                    ml = max(0, ml - temp_bonus)
                    mh += temp_bonus
                    current_p['bonus_range_next_turn'] = 0

                st.session_state.mod_low = ml
                st.session_state.mod_high = mh
                current_p['total_turns_taken'] += 1

                if card['name'] == "Road Closure":
                    st.session_state.turn_state = "road_closure"
                else:
                    st.session_state.turn_state = "move"
                if st.session_state.is_ragbraile:
                    _snapshot_active_ragbraile()
                st.rerun()

        elif st.session_state.turn_state == "road_closure":
            card = st.session_state.current_card
            st.write(f"🎲 Dice Rolls: **{st.session_state.r1}** and **{st.session_state.r2}**")
            st.warning(f"🃏 Power Card: {card['name']} — {card['reason']} (*{card['effect_text']}*)")

            if st.session_state.road_result_msg:
                st.info(st.session_state.road_result_msg)
                if st.button("End Turn"):
                    st.session_state.road_result_msg = None
                    st.session_state.turn_state = "roll"
                    st.session_state.current_idx = (st.session_state.current_idx + 1) % len(st.session_state.players)
                    if st.session_state.is_ragbraile:
                        _snapshot_active_ragbraile()
                    st.rerun()
            else:
                if st.session_state.dice_mode.startswith("Virtual"):
                    if st.button("🎲 Roll Die for Detour"):
                        rc_roll = random.randint(1, 6)
                        if rc_roll % 2 == 0:
                            msg = f"✨ You rolled an **Even ({rc_roll})**! You successfully bypass the road construction and stay in **{current_p['town']}**."
                        else:
                            msg = f"🚧 You rolled an **Odd ({rc_roll})**! The road construction forces you back to your previous town."
                            if len(current_p['history']) > 1:
                                current_p['history'].pop()
                                current_p['town'] = current_p['history'][-1]
                                if current_p['day_mileage_history']:
                                    sub_miles = current_p['day_mileage_history'].pop()
                                    current_p['base_mileage_tally'] = max(0, current_p['base_mileage_tally'] - sub_miles)
                        st.session_state.road_result_msg = msg
                        if st.session_state.is_ragbraile:
                            _snapshot_active_ragbraile()
                        st.rerun()
                else:
                    rc_input = st.number_input("Enter single die roll (1-6):", 1, 6, 1)
                    if st.button("Submit Detour Roll"):
                        if rc_input % 2 == 0:
                            msg = f"✨ You rolled an **Even ({rc_input})**! You successfully bypass the road construction and stay in **{current_p['town']}**."
                        else:
                            msg = f"🚧 You rolled an **Odd ({rc_input})**! The road construction forces you back to your previous town."
                            if len(current_p['history']) > 1:
                                current_p['history'].pop()
                                current_p['town'] = current_p['history'][-1]
                                if current_p['day_mileage_history']:
                                    sub_miles = current_p['day_mileage_history'].pop()
                                    current_p['base_mileage_tally'] = max(0, current_p['base_mileage_tally'] - sub_miles)
                        st.session_state.road_result_msg = msg
                        if st.session_state.is_ragbraile:
                            _snapshot_active_ragbraile()
                        st.rerun()

        elif st.session_state.turn_state == "move":
            card = st.session_state.current_card
            st.write(f"🎲 Dice Rolls: **{st.session_state.r1}** and **{st.session_state.r2}**")
            st.success(f"📊 **Base Daily Range:** {st.session_state.base_low} to {st.session_state.base_high} miles")
            st.info(f"🃏 Power Card: {card['name']} — {card['reason']} (*{card['effect_text']}*)")
            st.write(f"⚡ **Effective Range:** {st.session_state.mod_low} to {st.session_state.mod_high} miles")

            with st.expander("⚡ Use Special Abilities (One-Time Use)"):
                for ab_name, available in current_p['abilities'].items():
                    if is_solo and ab_name == "Thunderstorm":
                        continue

                    desc = ABILITY_DESCRIPTIONS[ab_name]
                    if available:
                        st.caption(f"**{ab_name}**: {desc}")
                        if st.button(f"Activate {ab_name}", help=f"Effect: {desc}", key=f"ab_btn_{ab_name}"):
                            current_p['abilities'][ab_name] = False
                            
                            if ab_name == "Slip & Slide Boost":
                                current_p['ability_penalty_pts'] += 10
                            elif ab_name == "Beekman's Energy Boost":
                                current_p['ability_penalty_pts'] += 5
                            
                            if not is_solo:
                                for op in st.session_state.players:
                                    if op['name'] != current_p['name']:
                                        op['bonus_range_next_turn'] = 5

                            if ab_name == "Beekman's Energy Boost":
                                st.session_state.mod_low = max(0, st.session_state.mod_low - 20)
                                st.session_state.mod_high += 20
                                st.success("Energy Boost applied! (-5 pts score penalty)")
                            elif ab_name == "Slip & Slide Boost":
                                st.session_state.mod_low = 0
                                st.session_state.mod_high = 9999
                                st.success("All mileage limits removed! (-10 pts score penalty)")
                            elif ab_name == "Thunderstorm":
                                opponents = [op for op in st.session_state.players if op['name'] != current_p['name']]
                                if opponents:
                                    target = opponents[0]
                                    if len(target['history']) > 1:
                                        target['history'].pop()
                                        target['town'] = target['history'][-1]
                                        if target['day_mileage_history']:
                                            sub_miles = target['day_mileage_history'].pop()
                                            target['base_mileage_tally'] = max(0, target['base_mileage_tally'] - sub_miles)
                                        st.warning(f"⚡ {target['name']} got struck by a Thunderstorm and moved back to {target['town']}!")
                            if st.session_state.is_ragbraile:
                                _snapshot_active_ragbraile()
                            st.rerun()
                    else:
                        st.caption(f"~~{ab_name}: Used~~")

            options = RAGBRAI_MAP.get(current_p['town'], {})
            any_valid = False
            
            st.markdown("#### Available Route Options:")
            for t_name, t_dist in options.items():
                in_range = st.session_state.mod_low <= t_dist <= st.session_state.mod_high
                if in_range:
                    any_valid = True
                    if st.button(f"Ride to {t_name} ({t_dist} mi)", key=f"route_{t_name}"):
                        extra_weave = random.randint(5, 10)
                        total_leg_miles = t_dist + extra_weave
                        current_p['base_mileage_tally'] += total_leg_miles
                        current_p['day_mileage_history'].append(total_leg_miles)
                        
                        current_p['history'].append(t_name)
                        current_p['town'] = t_name
                        days_ridden = len(current_p['history']) - 1
                        total_miles = calculate_player_mileage(current_p)
                        
                        if t_name in FINISH_TOWNS and days_ridden < 7:
                            current_p['reset_reason'] = f"🚨 **Overshot!** Reached finish town {t_name} on Day {days_ridden} (before Day 7). Select a new starting town to restart!"
                            st.session_state.phase = "select_start_single"
                            if st.session_state.is_ragbraile:
                                _snapshot_active_ragbraile()
                        elif days_ridden == 7:
                            if t_name in FINISH_TOWNS:
                                challenge_failed = False
                                fail_msg = ""
                                
                                if st.session_state.is_ragbraile:
                                    t1, t2 = st.session_state.ragbraile_pair
                                    if t1 not in current_p['history'] or t2 not in current_p['history']:
                                        challenge_failed = True
                                        fail_msg += f" Did not visit both mandatory towns ({t1} and {t2})."
                                else:
                                    if st.session_state.challenge_town_mode:
                                        if current_p['target_town'] not in current_p['history']:
                                            challenge_failed = True
                                            fail_msg += f" Did not visit required town **{current_p['target_town']}**."
                                            
                                    if st.session_state.challenge_mileage_mode:
                                        mileage_diff = abs(total_miles - current_p['target_mileage'])
                                        if mileage_diff > 35:
                                            challenge_failed = True
                                            fail_msg += f" Final mileage ({total_miles} mi) was not within 35 miles of target ({current_p['target_mileage']} mi)."

                                if challenge_failed:
                                    current_p['reset_reason'] = f"🚨 **Challenge Mode Failed!**{fail_msg} Select a new starting town to restart!"
                                    st.session_state.phase = "select_start_single"
                                    if st.session_state.is_ragbraile:
                                        _snapshot_active_ragbraile()
                                else:
                                    st.session_state.winner = current_p
                                    st.session_state.celebrate_win = True
                                    st.session_state.viewing_saved_ragbraile_result = None
                                    
                                    if current_p['name'] == st.session_state.current_username:
                                        u_prof = st.session_state.user_profile
                                        u_prof["games_finished"] = u_prof.get("games_finished", 0) + 1
                                        u_prof["total_miles_ridden"] = u_prof.get("total_miles_ridden", 0) + total_miles
                                        
                                        existing_towns = set(u_prof.get("completed_towns", []))
                                        existing_towns.update(current_p['history'])
                                        u_prof["completed_towns"] = list(existing_towns)
                                        
                                        today_str = _now_central().strftime("%Y-%m-%d")
                                        day_num = _now_central().timetuple().tm_yday
                                        
                                        if st.session_state.is_ragbraile:
                                            map_pen_saved = 15 if st.session_state.ragbraile_map_penalty_used else 0
                                            rb_scr = compute_ragbraile_score(
                                                current_p,
                                                st.session_state.ragbraile_map_penalty_used
                                            )
                                            u_prof["ragbraile_completions_count"] = u_prof.get("ragbraile_completions_count", 0) + 1
                                            u_prof["ragbraile_score_sum"] = u_prof.get("ragbraile_score_sum", 0) + rb_scr
                                            if rb_scr > u_prof.get("best_ragbraile_score", 0):
                                                u_prof["best_ragbraile_score"] = rb_scr

                                            solved_list = set(u_prof.get("ragbraile_days_solved", []))
                                            if day_num not in solved_list:
                                                solved_list.add(day_num)
                                                u_prof["ragbraile_days_solved"] = list(solved_list)
                                                
                                                last_date_str = u_prof.get("last_solved_date")
                                                today_date_obj = datetime.strptime(today_str, "%Y-%m-%d").date()
                                                if not last_date_str:
                                                    u_prof["current_streak"] = 1
                                                else:
                                                    last_date_obj = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                                                    if last_date_obj == today_date_obj - timedelta(days=1):
                                                        u_prof["current_streak"] = u_prof.get("current_streak", 0) + 1
                                                    elif last_date_obj < today_date_obj - timedelta(days=1):
                                                        u_prof["current_streak"] = 1
                                                u_prof["last_solved_date"] = today_str

                                            t1, t2 = st.session_state.ragbraile_pair
                                            u_prof.setdefault("ragbraile_results", {})[str(day_num)] = {
                                                "day_of_year": day_num,
                                                "ragbraile_pair": [t1, t2],
                                                "player_name": current_p["name"],
                                                "history": list(current_p["history"]),
                                                "miles": total_miles,
                                                "score": rb_scr,
                                                "total_turns_taken": current_p.get("total_turns_taken", 7),
                                                "ability_penalty_pts": current_p.get("ability_penalty_pts", 0),
                                                "map_penalty_pts": map_pen_saved,
                                            }
                                            u_prof.setdefault("recent_routes", []).append({
                                                "date": today_str,
                                                "mode": f"RAGBRAILE (Day {day_num})",
                                                "start": current_p['history'][0],
                                                "end": current_p['history'][-1],
                                                "miles": total_miles,
                                                "history": list(current_p['history']),
                                                "extra": f" — Targets: {t1}, {t2} | Score: {rb_scr}/100"
                                            })
                                            u_prof["active_ragbraile"] = None
                                            st.session_state.ragbraile_map_penalty_used = False
                                        else:
                                            u_prof["standard_wins"] = u_prof.get("standard_wins", 0) + 1
                                            
                                            mode_label = "Standard Game"
                                            challenge_descs = []
                                            if st.session_state.challenge_town_mode:
                                                challenge_descs.append(f"Mandatory Town: {current_p['target_town']}")
                                            if st.session_state.challenge_mileage_mode:
                                                challenge_descs.append(f"Target: {current_p['target_mileage']} miles")
                                            if challenge_descs:
                                                mode_label = f"Standard Game ({', '.join(challenge_descs)})"

                                            active_challenges_count = (1 if st.session_state.challenge_town_mode else 0) + (1 if st.session_state.challenge_mileage_mode else 0)
                                            if active_challenges_count == 2:
                                                pts_per_turn, base_score = 1, 107
                                            elif active_challenges_count == 1:
                                                pts_per_turn, base_score = 2, 114
                                            else:
                                                pts_per_turn, base_score = 3, 121
                                            turns_pen = current_p['total_turns_taken'] * pts_per_turn
                                            scr = max(0, base_score - turns_pen - current_p['ability_penalty_pts'])
                                            
                                            u_prof["total_score_sum"] = u_prof.get("total_score_sum", 0) + scr
                                            if scr > u_prof.get("best_score", 0):
                                                u_prof["best_score"] = scr
                                                
                                            u_prof.setdefault("recent_routes", []).append({
                                                "date": today_str,
                                                "mode": mode_label,
                                                "start": current_p['history'][0],
                                                "end": current_p['history'][-1],
                                                "miles": total_miles,
                                                "history": list(current_p['history']),
                                                "extra": f" — Score: {scr}/100"
                                            })
                                            
                                        st.session_state.user_profile = u_prof
                                        save_user_profile(st.session_state.current_username, u_prof)

                                    st.session_state.phase = "game_over"
                            else:
                                current_p['reset_reason'] = f"🚨 **Out of Time!** Day 7 ended in {t_name} instead of a finish town. Select a new starting town to restart!"
                                st.session_state.phase = "select_start_single"
                                if st.session_state.is_ragbraile:
                                    _snapshot_active_ragbraile()
                        else:
                            st.session_state.turn_state = "roll"
                            st.session_state.current_idx = (st.session_state.current_idx + 1) % len(st.session_state.players)
                            if st.session_state.is_ragbraile:
                                _snapshot_active_ragbraile()
                        
                        st.rerun()
                else:
                    st.text(f"{t_name} — {t_dist} mi [Out of Range]")

            if any_valid:
                st.markdown("---")
                if st.button(f"🏨 Stay in {current_p['town']} (Pass Turn)", help="Pass your turn without moving. Keeps same day, but adds 1 turn."):
                    current_p['total_turns_taken'] += 1
                    st.session_state.turn_state = "roll"
                    st.session_state.current_idx = (st.session_state.current_idx + 1) % len(st.session_state.players)
                    if st.session_state.is_ragbraile:
                        _snapshot_active_ragbraile()
                    st.rerun()
            else:
                st.warning("No routes are currently within your range!")
                if st.button("Step Back / Accept Being Stuck"):
                    if len(current_p['history']) <= 2:
                        current_p['reset_reason'] = f"🚨 **Stuck Early!** You had no valid moves. Select a town to restart!"
                        st.session_state.phase = "select_start_single"
                    else:
                        if len(current_p['history']) > 1:
                            current_p['history'].pop()
                            current_p['town'] = current_p['history'][-1]
                            if current_p['day_mileage_history']:
                                sub_miles = current_p['day_mileage_history'].pop()
                                current_p['base_mileage_tally'] = max(0, current_p['base_mileage_tally'] - sub_miles)
                        st.session_state.turn_state = "roll"
                        st.session_state.current_idx = (st.session_state.current_idx + 1) % len(st.session_state.players)
                    if st.session_state.is_ragbraile:
                        _snapshot_active_ragbraile()
                    st.rerun()

    with col_map:
        st.subheader("🗺️ Live Iowa Map")
        
        st.markdown("#### 🚴 Total Route Mileage Tracker")
        cols = st.columns(len(st.session_state.players))
        for idx, p in enumerate(st.session_state.players):
            p_miles = calculate_player_mileage(p)
            with cols[idx]:
                st.metric(label=f"{p['name']}'s Mileage", value=f"{p_miles} mi", delta=f"Day {len(p['history'])-1}")

        m = get_map(st.session_state.players)
        st_folium(m, width=650, height=480)

# ================= GAME OVER PHASE =================
elif st.session_state.phase == "game_over":
    winner = st.session_state.winner
    if st.session_state.get("celebrate_win"):
        st.balloons()
        st.session_state.celebrate_win = False

    saved_rb_view = st.session_state.get("viewing_saved_ragbraile_result")
    
    if st.session_state.is_ragbraile:
        t1, t2 = st.session_state.ragbraile_pair
        if saved_rb_view:
            st.header(f"🗓️ RAGBRAILE Day {st.session_state.ragbraile_day_of_year} Results — Targets: {t1} & {t2}")
            map_pen_pts = saved_rb_view.get("map_penalty_pts", 0)
            final_score = saved_rb_view.get("score", compute_ragbraile_score(winner, map_pen_pts >= 15))
            total_winning_miles = saved_rb_view.get("miles", calculate_player_mileage(winner))
        else:
            st.header(f"🎉 SUCCESS! You completed today's RAGBRAILE visiting {t1} & {t2}! 🎉")
            map_pen_pts = 15 if st.session_state.ragbraile_map_penalty_used else 0
            final_score = compute_ragbraile_score(winner, st.session_state.ragbraile_map_penalty_used)
            total_winning_miles = calculate_player_mileage(winner)
        pts_per_turn = 1
    else:
        st.header(f"🎉 CHAMPION: {winner['name']} wins RAGBRAI: The Game! 🎉")
        active_challenges_count = (1 if st.session_state.challenge_town_mode else 0) + (1 if st.session_state.challenge_mileage_mode else 0)
        if active_challenges_count == 2:
            pts_per_turn = 1
            base_score = 107
        elif active_challenges_count == 1:
            pts_per_turn = 2
            base_score = 114
        else:
            pts_per_turn = 3
            base_score = 121

        turns_penalty = winner['total_turns_taken'] * pts_per_turn
        raw_score = base_score - turns_penalty - winner['ability_penalty_pts']
        final_score = max(0, raw_score)
        map_pen_pts = 0
        total_winning_miles = calculate_player_mileage(winner)
    
    col_stats, col_map = st.columns([1, 1])
    
    with col_stats:
        if st.session_state.is_ragbraile:
            st.metric(
                "Final RAGBRAILE Score",
                f"{final_score} / 100",
                f"100 base - ({winner['total_turns_taken'] - 7} extra turns × 1 pt each) - {winner['ability_penalty_pts']} ability pts - {map_pen_pts} map pts"
            )
        else:
            st.metric(
                "Final Score",
                f"{final_score} / 100",
                f"100 base - ({winner['total_turns_taken'] - 7} extra turns × {pts_per_turn} pts each) - {winner['ability_penalty_pts']} ability pts"
            )
        st.metric("Total Route Distance", f"{total_winning_miles} miles")

        st.subheader("📜 Winning Route Recap (8 Days Total):")
        for idx, t in enumerate(winner['history']):
            prefix = f"Day {idx} (Finish):" if idx == 7 else f"Day {idx}:"
            st.write(f"- {prefix} **{t}**")

        route_text = " ➜ ".join(winner["history"])

        if st.session_state.is_ragbraile:
            share_text = (
                f"🚴 RAGBRAILE Day {st.session_state.ragbraile_day_of_year}\n"
                f"Score: {final_score}/100\n"
                f"Route: {route_text}"
            )
        else:
            share_text = (
                f"🚴 RAGBRAI: The Game\n"
                f"Score: {final_score}/100\n"
                f"Route: {route_text}"
            )

        st.components.v1.html(
            f"""
            <button
                onclick="navigator.clipboard.writeText(`{share_text}`)"
                style="
                    background:#ff4b4b;
                    color:white;
                    border:none;
                    padding:10px 18px;
                    border-radius:8px;
                    font-weight:bold;
                    cursor:pointer;"
            >
                📋 Copy Result
            </button>
            """,
            height=50,
        )

        if st.button("Back to Home"):
            st.session_state.is_ragbraile = False
            st.session_state.viewing_saved_ragbraile_result = None
            st.session_state.nav_stack = []
            st.session_state.phase = "setup"
            st.rerun()
            
    with col_map:
        st.subheader("🗺️ Winning Route Map")
        m = get_map([winner])
        st_folium(m, width=650, height=480)
