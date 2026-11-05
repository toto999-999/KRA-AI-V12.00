import os
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

VERSION = "KRA전국 승부예상AI_V12.00"
API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "http://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"

KST = timezone(timedelta(hours=9))

MEET_CONFIG = [
    ("1", "서울"),
    ("4", "영천"),
    ("2", "제주"),
    ("3", "부산경남")
]

JOCKEY_RATES = {
    "문세영": 33.2, "김용근": 24.5, "빅투아르": 25.1, "유승완": 21.0,
    "송재철": 19.5, "이혁": 19.2, "임다빈": 18.5, "장추열": 18.0,
    "임기원": 17.5, "이동하": 16.0, "조인권": 21.4, "마이아": 22.0,
    "서승운": 31.5, "최시대": 26.8, "다나카": 25.4, "다비드": 24.2,
    "유현명": 23.8, "정도윤": 22.5, "김혜선": 20.8, "김동영": 17.8,
    "이성재": 16.5, "송경윤": 15.2, "전진구": 14.8, "김어수": 14.5, "손경민": 14.0,
    "전현준": 26.5, "한영민": 24.2, "임재광": 21.8, "양민재": 19.5,
    "원유일": 18.2, "박재희": 17.5, "곽용남": 16.8, "김한남": 16.0,
    "강수한": 15.5, "이동준": 15.0, "안득수": 20.5, "정명일": 19.0
}

TRAINER_RATES = {
    "서홍수": 24.5, "송문길": 21.5, "배휴준": 20.8, "정호익": 19.5,
    "최용건": 19.0, "박재우": 17.2, "이강서": 16.8, "전승규": 16.0, "서인석": 15.0,
    "김영관": 28.0, "라이스": 25.2, "민장기": 22.1, "구영준": 18.5,
    "김도현": 18.2, "안우성": 18.0, "임성실": 17.5, "백광열": 18.8, "강은석": 15.5,
    "심도연": 23.5, "김태준": 21.0, "강대은": 20.5, "김길홍": 18.5,
    "윤덕상": 17.8, "김대연": 17.2, "이준호": 16.5, "문성호": 15.8, "고성동": 22.0
}

def clean_name(val):
    if not val: return ""
    v = re.sub(r'[\(\[\{].*?[\)\]\}]', '', str(val))
    return re.sub(r'[^가-힣a-zA-Z]', '', v).strip()

def sanitize_jockey_and_trainer(jockey, trainer):
    jk = clean_name(jockey)
    tr = clean_name(trainer)
    if tr == "문세영":
        if jk in TRAINER_RATES: jk, tr = tr, jk
        else: tr, jk = "관리팀", "문세영"
    if tr in ["서승운", "김용근", "빅투아르", "유승완", "최시대", "다나카"] and jk in TRAINER_RATES:
        jk, tr = tr, jk
    return jk, tr

def get_norm_meet(name):
    if name in ["부산경남", "영천", "부경"]: return "부산경남"
    return name

def scrape_kra_timetable_and_distances(date_str):
    url = f"https://todayrace.kra.co.kr/race/raceTimeTable.do?searchDate={date_str}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    timeline_order = []
    dist_map = {}
    
    try:
        # 타임아웃을 4초로 단축하여 불필요한 대기 방지
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as res:
            html = res.read().decode('utf-8', errors='ignore')
        
        matches = re.findall(r'(제주|서울|부경|부산경남|영천)\s*(\d+)경주.*?(\d{3,4})\s*M', html, re.DOTALL)
        for idx, (m_name, r_no, dist) in enumerate(matches):
            norm_meet = "부산경남" if m_name in ["부경", "영천"] else m_name
            r_num = str(int(r_no))
            dist_map[(str(date_str), norm_meet, r_num)] = dist
            if m_name == "영천":
                dist_map[(str(date_str), "영천", r_num)] = dist

            item_tuple = (str(date_str), norm_meet, r_num)
            if item_tuple not in timeline_order:
                timeline_order.append(item_tuple)
    except:
        pass
        
    return timeline_order, dist_map

LIVE_TIMELINE_CACHE = {}
LIVE_DIST_CACHE = {}

def fetch_meet_data(meet_code, meet_name, date_str):
    global LIVE_TIMELINE_CACHE, LIVE_DIST_CACHE
    if date_str not in LIVE_DIST_CACHE:
        t_order, d_map = scrape_kra_timetable_and_distances(date_str)
        LIVE_TIMELINE_CACHE[date_str] = t_order
        LIVE_DIST_CACHE[date_str] = d_map

    live_dist_map = LIVE_DIST_CACHE.get(date_str, {})

    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "180",
        "meet": meet_code,
        "rc_date": date_str
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        if not items: return []

        races = {}
        for it in items:
            def gv(tag_list):
                for t in tag_list:
                    n = it.find(t)
                    if n is not None and n.text and n.text.strip(): return n.text.strip()
                    for child in it:
                        tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        if tag_name.lower() == t.lower() and child.text and child.text.strip():
                            return child.text.strip()
                return ""

            raw_rc_no = gv(["rcNo", "rc_no"]) or "1"
            rc_no = str(int(raw_rc_no)) if raw_rc_no.isdigit() else raw_rc_no
            raw_gate = gv(["chulNo", "chul_no", "gateNo", "hrNo"]) or "0"
            gate = str(int(raw_gate)) if raw_gate.isdigit() else raw_gate
            name = clean_name(gv(["hrName", "hr_name"]) or "경주마")

            raw_jockey = gv(["jkName", "jk_name", "jockeyName", "jockey"]) or "기수"
            raw_trainer = gv(["trName", "tr_name", "trainerName", "trainer"]) or "조교사"
            jockey, trainer = sanitize_jockey_and_trainer(raw_jockey, raw_trainer)

            raw_dist = gv(["rcDist", "rc_dist", "distance", "dist", "rc_distance"]) or ""
            clean_dist = re.sub(r'[^0-9]', '', raw_dist)

            weight = gv(["wgBudam", "wg_budam", "weight"]) or "55.0"
            track = gv(["track", "track_state", "trackCond", "weather"]) or "양호"
            rc_time = gv(["rcTime", "rc_time", "record", "rcRecord", "ordTime"]) or ""
            past_time = gv(["bestRecord", "bestRcTime", "recentRecord", "recentRcTime", "preRcTime"]) or ""
            g1f_time = gv(["g1f", "g1f_time", "g1fTime", "g1fRecord", "g_1f"]) or ""
            win_odds = gv(["winOdds", "win_odds", "win_rate", "odds"]) or "0"
            pre_ord = gv(["preOrd", "pre_ord", "recentOrd", "preRcOrd"]) or ""
            rc_cnt = gv(["rcCnt", "rc_cnt", "totRcCnt"]) or "0"
            ord1_cnt = gv(["ord1Cnt", "ord1_cnt", "totOrd1Cnt"]) or "0"
            ord2_cnt = gv(["ord2Cnt", "ord2_cnt", "totOrd2Cnt"]) or "0"

            s1f_rank = gv(["g1p", "s1f", "g1pRank", "ord1p"]) or ""
            is_front = False
            if s1f_rank in ["1", "2", "01", "02"]: is_front = True
            elif str(pre_ord).strip() in ["1", "2", "01", "02"] and int(gate) <= 4: is_front = True

            ord_no = "-"
            isValidTime = len(rc_time.strip()) >= 3 and (":" in rc_time or "." in rc_time)
            direct_ord = gv(["ordNo", "ord_no", "ord", "rc_ord", "rcOrd", "rank", "rankNo", "chaksun"])
            if isValidTime and direct_ord and direct_ord.isdigit() and 0 < int(direct_ord) <= 20:
                ord_no = str(int(direct_ord))

            key = f"{meet_name}_{rc_no}_{date_str}"
            if key not in races:
                norm_m = get_norm_meet(meet_name)
                dist_lookup = live_dist_map.get((str(date_str), norm_m, str(int(rc_no))))
                if not dist_lookup and clean_dist and int(clean_dist) >= 800:
                    dist_lookup = clean_dist
                if not dist_lookup:
                    dist_lookup = "1200"

                races[key] = {
                    "meet_code": meet_code,
                    "meet_name": meet_name,
                    "race_no": rc_no,
                    "race_date": date_str,
                    "distance": dist_lookup,
                    "track": track,
                    "version": VERSION,
                    "horses": []
                }

            if any(h["gate"] == gate or h["name"] == name for h in races[key]["horses"]):
                continue

            races[key]["horses"].append({
                "gate": gate, "name": name, "jockey": jockey, "trainer": trainer,
                "weight": weight, "track": track, "rc_time": rc_time, "past_time": past_time,
                "g1f_time": g1f_time, "win_odds": win_odds, "pre_ord": pre_ord,
                "rc_cnt": rc_cnt, "ord1_cnt": ord1_cnt, "ord2_cnt": ord2_cnt,
                "is_front": is_front, "actual_ord": ord_no
            })

        for r in races.values():
            norm_m = get_norm_meet(r["meet_name"])
            real_d = live_dist_map.get((str(r["race_date"]), norm_m, str(int(r["race_no"]))))
            if real_d:
                r["distance"] = real_d

        return list(races.values())

    except Exception as e:
        return []

def sync_active_races():
    now = datetime.now(KST)
    existing_races = {}

    cutoff_date = (now - timedelta(days=70)).strftime("%Y%m%d")

    if os.path.exists("race_data.json"):
        try:
            with open("race_data.json", "r", encoding="utf-8") as f:
                old_list = json.load(f)
                for r in old_list:
                    r_date = str(r.get('race_date', ''))
                    if r_date >= cutoff_date:
                        k = f"{r_date}_{r.get('meet_name')}_{r.get('race_no')}"
                        existing_races[k] = r
        except:
            existing_races = {}

    # 🎯 [초고속 최적화] 경마가 없는 평일(월·화·수)은 아예 제외!
    # 실제 경마일(금/토/일)과 오늘(목)만 골라서 수집하므로 속도가 4배 이상 빨라집니다.
    target_dates = []
    
    # 1. 지난 7일 중 금, 토, 일만 추출 (실제 결과 복기용)
    for i in range(7, 0, -1):
        d_obj = now - timedelta(days=i)
        if d_obj.weekday() in [4, 5, 6]: # 금(4), 토(5), 일(6)
            target_dates.append(d_obj.strftime("%Y%m%d"))
            
    # 2. 오늘 날짜 추가
    target_dates.append(now.strftime("%Y%m%d"))
    
    # 3. 다가오는 금, 토, 일 날짜 추가 (이번 주 확정 출마표)
    for i in range(1, 5):
        d_obj = now + timedelta(days=i)
        if d_obj.weekday() in [4, 5, 6]:
            target_dates.append(d_obj.strftime("%Y%m%d"))

    unique_dates = sorted(list(set(target_dates)))
    print(f"⚡ 초고속 실시간 수집 대상 경마일: {unique_dates}")

    for dt in unique_dates:
        t_order, d_map = scrape_kra_timetable_and_distances(dt)
        LIVE_TIMELINE_CACHE[dt] = t_order
        LIVE_DIST_CACHE[dt] = d_map

        for m_code, m_name in MEET_CONFIG:
            res = fetch_meet_data(m_code, m_name, dt)
            for r in res:
                norm_m = get_norm_meet(r.get("meet_name"))
                real_d = d_map.get((str(dt), norm_m, str(int(r.get("race_no")))))
                if real_d:
                    r["distance"] = real_d
                    for h in r.get("horses", []):
                        h["distance"] = real_d

                k = f"{r.get('race_date')}_{r.get('meet_name')}_{r.get('race_no')}"
                if k in existing_races:
                    old_race = existing_races[k]
                    if old_race.get("saved_derby"):
                        r["saved_derby"] = old_race["saved_derby"]
                    for new_h in r.get("horses", []):
                        old_h = next((h for h in old_race.get("horses", []) if str(h.get("gate")) == str(new_h.get("gate"))), None)
                        if old_h:
                            if old_h.get("saved_odds"):
                                new_h["saved_odds"] = old_h["saved_odds"]
                            if new_h.get("actual_ord") == "-" and old_h.get("actual_ord") not in ["-", "", None]:
                                new_h["actual_ord"] = old_h.get("actual_ord")
                existing_races[k] = r

    final_list = [r for k, r in existing_races.items() if str(r.get("race_date", "")) >= cutoff_date]
    
    def get_timeline_weight(race_item):
        dt = race_item["race_date"]
        m = get_norm_meet(race_item["meet_name"])
        r_no = str(int(race_item["race_no"]))
        
        if dt in LIVE_TIMELINE_CACHE:
            t_list = LIVE_TIMELINE_CACHE[dt]
            target_tuple = (dt, m, r_no)
            if target_tuple in t_list:
                return t_list.index(target_tuple)
        
        meet_fallback = {"제주": 1, "부산경남": 2, "영천": 2, "서울": 3}
        return 9999 + (meet_fallback.get(race_item["meet_name"], 9) * 100) + int(race_item["race_no"])

    final_list.sort(key=lambda x: (x["race_date"], get_timeline_weight(x)))
    return final_list

def main():
    if not API_KEY:
        print("❌ KRA_API_KEY 미설정")
        return

    all_races = sync_active_races()

    if all_races:
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"🎉 성공: 초고속 동기화 완료! (총 {len(all_races)}개 경주)")

if __name__ == "__main__":
    main()
