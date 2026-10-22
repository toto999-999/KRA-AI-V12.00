import os
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from collections import Counter
import time

# =========================================================================
# KRA전국 승부예상AI_V12.00 (거리 파싱 보정 완료)
# =========================================================================
VERSION = "KRA전국 승부예상AI_V12.00"
API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "http://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"
KST = timezone(timedelta(hours=9))

MEET_CONFIG = [("1", "서울"), ("4", "영천"), ("2", "제주"), ("3", "부산경남")]

OFFICIAL_DISTANCES = {
    ("20261016", "제주", "1"): "1000", ("20261016", "제주", "2"): "1000", ("20261016", "제주", "3"): "1000", 
    ("20261016", "제주", "4"): "1110", ("20261016", "제주", "5"): "1110", ("20261016", "제주", "6"): "1200", 
    ("20261016", "제주", "7"): "1200", ("20261016", "부산경남", "1"): "1000", ("20261016", "부산경남", "2"): "1200",
    ("20261016", "부산경남", "3"): "1300", ("20261016", "부산경남", "4"): "1400", ("20261016", "부산경남", "5"): "1800",
    ("20261016", "부산경남", "6"): "1200", ("20261016", "부산경남", "7"): "1800", ("20261016", "부산경남", "8"): "1800", 
    ("20261016", "부산경남", "9"): "1200", ("20261017", "서울", "1"): "1200", ("20261017", "서울", "2"): "1400",
    ("20261017", "서울", "3"): "1300", ("20261017", "서울", "4"): "1200", ("20261017", "서울", "5"): "1700",
    ("20261017", "서울", "6"): "1300", ("20261017", "서울", "7"): "1800", ("20261017", "서울", "8"): "1400",
    ("20261017", "서울", "9"): "1200", ("20261017", "서울", "10"): "1800"
}

JOCKEY_RATES = {"문세영": 33.2, "김용근": 24.5, "빅투아르": 25.1, "유승완": 21.0, "송재철": 19.5, "이혁": 19.2, "임다빈": 18.5, "장추열": 18.0, "임기원": 17.5, "이동하": 16.0, "조인권": 21.4, "마이아": 22.0, "서승운": 31.5, "최시대": 26.8, "다나카": 25.4, "다비드": 24.2, "유현명": 23.8, "정도윤": 22.5, "김혜선": 20.8, "김동영": 17.8}
TRAINER_RATES = {"서홍수": 24.5, "송문길": 21.5, "배휴준": 20.8, "정호익": 19.5, "최용건": 19.0, "박재우": 17.2, "이강서": 16.8, "전승규": 16.0, "서인석": 15.0, "김영관": 28.0, "라이스": 25.2, "민장기": 22.1, "구영준": 18.5, "김도현": 18.2, "안우성": 18.0, "임성실": 17.5, "백광열": 18.8}

def clean_name(val):
    if not val: return ""
    v = re.sub(r'[\(\[\{].*?[\)\]\}]', '', str(val))
    return re.sub(r'[^가-힣a-zA-Z]', '', v).strip()

def sanitize_jockey_and_trainer(jockey, trainer):
    jk = clean_name(jockey)
    tr = clean_name(trainer)
    return jk, tr

def fetch_meet_data(meet_code, meet_name, date_str):
    params = {"serviceKey": API_KEY, "pageNo": "1", "numOfRows": "200", "meet": meet_code, "rc_date": date_str}
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=10) as response:
            root = ET.fromstring(response.read())
            items = root.findall(".//item")
            if not items: return []
            races = {}
            for it in items:
                def gv(tags):
                    for t in tags:
                        val = it.find(t)
                        if val is not None and val.text: return val.text.strip()
                    return ""
                
                rc_no = str(int(gv(["rcNo", "rc_no"]) or "1"))
                gate = str(int(gv(["chulNo", "chul_no", "gateNo"]) or "0"))
                
                # 거리 파싱 보정
                raw_dist = gv(["rcDist", "rc_dist", "distance", "dist", "rc_distance", "distName"])
                clean_dist = re.sub(r'[^0-9]', '', raw_dist)
                dist_val = OFFICIAL_DISTANCES.get((date_str, meet_name, rc_no)) or (clean_dist if (clean_dist and int(clean_dist) >= 800) else "1200")

                key = f"{meet_name}_{rc_no}_{date_str}"
                if key not in races:
                    races[key] = {"meet_name": meet_name, "race_no": rc_no, "race_date": date_str, "distance": dist_val, "horses": []}
                
                races[key]["horses"].append({
                    "gate": gate, "name": clean_name(gv(["hrName"])), "jockey": clean_name(gv(["jkName"])), 
                    "trainer": clean_name(gv(["trName"])), "weight": gv(["wgBudam"]) or "55.0",
                    "win_prob": 10.0, "is_front": False, "early_rank": 1, "late_rank": 1
                })
            return list(races.values())
    except: return []

def sync_5weeks_archive():
    now = datetime.now(KST)
    existing_races = {}
    if os.path.exists("race_data.json"):
        with open("race_data.json", "r", encoding="utf-8") as f:
            for r in json.load(f): existing_races[f"{r['race_date']}_{r['meet_name']}_{r['race_no']}"] = r
    
    for i in range(-5, 5):
        dt = (now + timedelta(days=i)).strftime("%Y%m%d")
        for m_code, m_name in MEET_CONFIG:
            for r in fetch_meet_data(m_code, m_name, dt):
                existing_races[f"{r['race_date']}_{r['meet_name']}_{r['race_no']}"] = r
    return list(existing_races.values())

def main():
    if not API_KEY: return
    all_races = sync_5weeks_archive()
    with open("race_data.json", "w", encoding="utf-8") as f:
        json.dump(all_races, f, ensure_ascii=False, indent=2)
    print("갱신 완료")

if __name__ == "__main__":
    main()
