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
# 프로그램 명칭: KRA전국 승부예상AI_V12.00 (마사회 오늘의 경주 실시간 타임라인 & 거리 엔진)
# =========================================================================
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

# =========================================================================
# 🎯 [핵심] 마사회 '오늘의 경주' 공식 웹사이트에서 실시간 발주순서 및 거리 싹 다 크롤링!
# =========================================================================
def scrape_kra_timetable_and_distances(date_str):
    url = f"https://todayrace.kra.co.kr/race/raceTimeTable.do?searchDate={date_str}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    timeline_order = []
    dist_map = {}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as res:
            html = res.read().decode('utf-8', errors='ignore')
        
        # HTML에서 '제주1경주 ... 1000M' 또는 발주 시간대 패턴 매칭
        # 마사회 웹의 실제 표출 순서(타임라인) 그대로 추출
        matches = re.findall(r'(제주|서울|부경|부산경남|영천)\s*(\d+)경주.*?(\d{3,4})\s*M', html, re.DOTALL)
        
        for idx, (m_name, r_no, dist) in enumerate(matches):
            norm_meet = "부산경남" if m_name in ["부경", "영천"] else m_name
            r_num = str(int(r_no))
            
            dist_map[(str(date_str), norm_meet, r_num)] = dist
            if m_name == "영천":
                dist_map[(str(date_str), "영천", r_num)] = dist

            # 마사회 웹에 나타난 순서 그대로 타임라인 리스트에 등록 (중복 방지)
            item_tuple = (str(date_str), norm_meet, r_num)
            if item_tuple not in timeline_order:
                timeline_order.append(item_tuple)
                
        print(f"📡 [마사회 실시간 타임라인 크롤링 성공] {date_str}: {len(timeline_order)}개 경주 순서 확보")
    except Exception as e:
        print(f"⚠️ 실시간 타임라인 크롤링 예외 ({date_str}): {e}")
        
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
        with urllib.request.urlopen(req, timeout=12) as response:
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
            direct_ord = gv(["ordNo", "ord_no", "ord", "rc_ord", "rcOrd", "rank", "rankNo", "chaksun"])
            if direct_ord and direct_ord.isdigit() and int(direct_ord) > 0 and int(direct_ord) <= 20:
                ord_no = str(int(direct_ord))
            else:
                for child in it:
                    tag_low = (child.tag.split("}")[-1] if "}" in child.tag else child.tag).lower()
                    if any(ex in tag_low for ex in ["pre", "cnt", "s1f", "g1p", "g2p", "g3p", "g4p", "pass", "time", "rec"]):
                        continue
                    if any(k in tag_low for k in ["ord", "rank", "plc", "place", "chak"]):
                        txt = child.text.strip() if child.text else ""
                        if txt.isdigit() and int(txt) > 0 and int(txt) <= 20:
                            ord_no = str(int(txt))
                            break

            key = f"{meet_name}_{rc_no}_{date_str}"
            if key not in races:
                # 🎯 [거리 확정 3중 방어막] 마사회 웹 크롤링 거리 ➔ API 거리 ➔ 기본값
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

            dist = int(r["distance"])
            meet = r["meet_name"]

            raw_scores = []
            for h in r["horses"]:
                g = int(h["gate"]) if str(h["gate"]).isdigit() else 5
                try: clean_w = float(re.sub(r'[^0-9.]', '', str(h["weight"])))
                except: clean_w = 55.0

                tot_rc = int(re.sub(r'[^0-9]', '', str(h.get("rc_cnt", "0"))) or 0)
                ord1_cnt = int(re.sub(r'[^0-9]', '', str(h.get("ord1_cnt", "0"))) or 0)
                ord2_cnt = int(re.sub(r'[^0-9]', '', str(h.get("ord2_cnt", "0"))) or 0)
                quinella_rate = round(((ord1_cnt + ord2_cnt) / tot_rc) * 100, 1) if tot_rc >= 3 else 20.0
                win_rate = round((ord1_cnt / tot_rc) * 100, 1) if tot_rc >= 3 else 10.0

                raw_jk = JOCKEY_RATES.get(h["jockey"], 12.0)
                tr_rate = TRAINER_RATES.get(h["trainer"], 14.0)

                early_score = 0.0
                if h["is_front"]: early_score += 30.0
                if g <= 3: early_score += 15.0
                elif g <= 5: early_score += 8.0
                early_score += (55.0 - clean_w) * 2.0
                early_score += (raw_jk * 0.35)
                h["early_score"] = round(early_score, 1)

                late_score = 0.0
                if not h["is_front"]: late_score += 20.0
                if 4 <= g <= 8: late_score += 10.0
                late_score += (55.0 - clean_w) * 2.5
                late_score += (tr_rate * 0.4) + (raw_jk * 0.3)
                if get_norm_meet(meet) == "부산경남" and dist >= 1400: late_score += 12.0
                h["late_score"] = round(late_score, 1)

                power = 25.0 + (win_rate * 0.8) + (quinella_rate * 0.3) + (raw_jk * 0.35) + (tr_rate * 0.35)
                power += (55.0 - clean_w) * 2.0

                if meet == "제주" and g <= 3: power += 8.0
                elif dist <= 1300 and g <= 3: power += 4.0
                elif get_norm_meet(meet) == "부산경남" and dist >= 1400 and (not h["is_front"]): power += 5.0

                raw_scores.append(max(5.0, power))

            horses_by_early = sorted(r["horses"], key=lambda x: x["early_score"], reverse=True)
            for rank, horse in enumerate(horses_by_early, 1):
                horse["early_rank"] = rank
                if rank <= 5: horse.setdefault("ai_tags", []).append(f"⚡초반 {rank}위")

            horses_by_late = sorted(r["horses"], key=lambda x: x["late_score"], reverse=True)
            for rank, horse in enumerate(horses_by_late, 1):
                horse["late_rank"] = rank
                if rank <= 5: horse.setdefault("ai_tags", []).append(f"🚀후반 {rank}위")

            total_power = sum(raw_scores) or 100.0
            for idx, h in enumerate(r["horses"]):
                prob = round((raw_scores[idx] / total_power) * 100, 1)
                h["win_prob"] = prob
                h["place_prob"] = round(min(85.0, prob * 2.4), 1)
                h["pure_score"] = round(raw_scores[idx], 1)

            r["horses"].sort(key=lambda x: x["win_prob"], reverse=True)

        return list(races.values())

    except Exception as e:
        print(f"[{meet_name}] 통신 에러: {e}")
        return []

def sync_5weeks_archive():
    now = datetime.now(KST)
    existing_races = {}
    if os.path.exists("race_data.json"):
        try:
            with open("race_data.json", "r", encoding="utf-8") as f:
                old_list = json.load(f)
                for r in old_list:
                    k = f"{r.get('race_date')}_{r.get('meet_name')}_{r.get('race_no')}"
                    existing_races[k] = r
            print(f"📦 기존 저장소 로드 완료: {len(existing_races)}개 경주")
        except:
            existing_races = {}

    dates_to_fetch = []
    for i in range(7, 0, -1):
        dates_to_fetch.append((now - timedelta(days=i)).strftime("%Y%m%d"))
    dates_to_fetch.append(now.strftime("%Y%m%d"))
    for i in range(1, 10):
        dates_to_fetch.append((now + timedelta(days=i)).strftime("%Y%m%d"))

    unique_dates = sorted(list(set(dates_to_fetch)))
    print(f"🔄 V12.00 수집 대상 전체 날짜: {unique_dates}")

    for dt in unique_dates:
        # 해당 날짜의 마사회 실시간 타임라인 순서 목록 확보
        t_order, d_map = scrape_kra_timetable_and_distances(dt)
        
        for m_code, m_name in MEET_CONFIG:
            res = fetch_meet_data(m_code, m_name, dt)
            for r in res:
                # 실시간 크롤링된 정확한 거리 덮어쓰기
                norm_m = get_norm_meet(r.get("meet_name"))
                real_d = d_map.get((str(dt), norm_m, str(int(r.get("race_no")))))
                if real_d:
                    r["distance"] = real_d
                    for h in r.get("horses", []):
                        h["distance"] = real_d

                k = f"{r.get('race_date')}_{r.get('meet_name')}_{r.get('race_no')}"
                if k in existing_races:
                    old_race = existing_races[k]
                    for new_h in r.get("horses", []):
                        if new_h.get("actual_ord") == "-":
                            old_h = next((h for h in old_race.get("horses", []) if h.get("gate") == new_h.get("gate")), None)
                            if old_h and old_h.get("actual_ord") not in ["-", "", None]:
                                new_h["actual_ord"] = old_h.get("actual_ord")
                existing_races[k] = r

    cutoff_date = (now - timedelta(days=35)).strftime("%Y%m%d")
    final_list = [r for k, r in existing_races.items() if str(r.get("race_date", "")) >= cutoff_date]
    
    # 🎯 [핵심] 마사회 '오늘의 경주' 발주 시간순(타임라인) 그대로 완벽 정렬!
    def get_timeline_weight(race_item):
        dt = race_item["race_date"]
        m = get_norm_meet(race_item["meet_name"])
        r_no = str(int(race_item["race_no"]))
        
        if dt in LIVE_TIMELINE_CACHE:
            t_list = LIVE_TIMELINE_CACHE[dt]
            target_tuple = (dt, m, r_no)
            if target_tuple in t_list:
                return t_list.index(target_tuple) # 마사회 웹에 나타난 실제 순서 번호 반환!
        
        # 만약 웹 크롤링 목록에 없으면 기본 정렬 (제주 ➔ 부경 ➔ 서울, 라운드순)
        meet_fallback = {"제주": 1, "부산경남": 2, "영천": 2, "서울": 3}
        return 9999 + (meet_fallback.get(race_item["meet_name"], 9) * 100) + int(race_item["race_no"])

    final_list.sort(key=lambda x: (x["race_date"], get_timeline_weight(x)))
    return final_list

def main():
    if not API_KEY:
        print("❌ KRA_API_KEY 미설정")
        return

    all_races = sync_5weeks_archive()

    if all_races:
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"🎉 성공: [{VERSION}] 마사회 실시간 웹 타임라인 & 거리 동기화 완료! (총 {len(all_races)}개 경주)")
    else:
        print("❌ 데이터를 가져오지 못했습니다.")

if __name__ == "__main__":
    main()
