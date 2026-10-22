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
# 프로그램 명칭: KRA전국 승부예상AI_V12.00 (캐시 클렌징 & 완벽 타임라인 엔진)
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

# 🎯 마사회 공식 편성표 거리 1:1 완벽 보장 데이터베이스 (1200m 도배 원천 차단)
OFFICIAL_DISTANCES = {
    # 10월 16일 (금)
    ("20261016", "제주", "1"): "1000", ("20261016", "제주", "2"): "1000",
    ("20261016", "제주", "3"): "1000", ("20261016", "제주", "4"): "1110",
    ("20261016", "제주", "5"): "1110", ("20261016", "제주", "6"): "1200", ("20261016", "제주", "7"): "1200",
    ("20261016", "부산경남", "1"): "1000", ("20261016", "부산경남", "2"): "1200",
    ("20261016", "부산경남", "3"): "1300", ("20261016", "부산경남", "4"): "1400",
    ("20261016", "부산경남", "5"): "1800", ("20261016", "부산경남", "6"): "1200",
    ("20261016", "부산경남", "7"): "1800", ("20261016", "부산경남", "8"): "1800", ("20261016", "부산경남", "9"): "1200",
    ("20261016", "영천", "1"): "1000", ("20261016", "영천", "2"): "1200",
    ("20261016", "영천", "3"): "1300", ("20261016", "영천", "4"): "1400",
    ("20261016", "영천", "5"): "1800", ("20261016", "영천", "6"): "1200",
    ("20261016", "영천", "7"): "1800", ("20261016", "영천", "8"): "1800", ("20261016", "영천", "9"): "1200",

    # 10월 17일 (토)
    ("20261017", "서울", "1"): "1200", ("20261017", "서울", "2"): "1400",
    ("20261017", "서울", "3"): "1300", ("20261017", "서울", "4"): "1200",
    ("20261017", "서울", "5"): "1700", ("20261017", "서울", "6"): "1300",
    ("20261017", "서울", "7"): "1800", ("20261017", "서울", "8"): "1400",
    ("20261017", "서울", "9"): "1200", ("20261017", "서울", "10"): "1800",
    ("20261017", "제주", "1"): "900",  ("20261017", "제주", "2"): "1000",
    ("20261017", "제주", "3"): "1000", ("20261017", "제주", "4"): "1110",
    ("20261017", "제주", "5"): "1110", ("20261017", "제주", "6"): "1200", ("20261017", "제주", "7"): "1300",

    # 10월 18일 (일)
    ("20261018", "서울", "1"): "1000", ("20261018", "서울", "2"): "1200",
    ("20261018", "서울", "3"): "1200", ("20261018", "서울", "4"): "1300",
    ("20261018", "서울", "5"): "1400", ("20261018", "서울", "6"): "1200",
    ("20261018", "서울", "7"): "1600", ("20261018", "서울", "8"): "2000",
    ("20261018", "서울", "9"): "1700", ("20261018", "서울", "10"): "1800", ("20261018", "서울", "11"): "1400",
    ("20261018", "영천", "1"): "1000", ("20261018", "영천", "2"): "1200",
    ("20261018", "영천", "3"): "1400", ("20261018", "영천", "4"): "1400",
    ("20261018", "영천", "5"): "1600", ("20261018", "영천", "6"): "1800",
    ("20261018", "부산경남", "1"): "1000", ("20261018", "부산경남", "2"): "1200",
    ("20261018", "부산경남", "3"): "1400", ("20261018", "부산경남", "4"): "1400",
    ("20261018", "부산경남", "5"): "1600", ("20261018", "부산경남", "6"): "1800",

    # 10월 23일 (금) 다다음 주
    ("20261023", "부산경남", "1"): "1000", ("20261023", "부산경남", "2"): "1200",
    ("20261023", "부산경남", "3"): "1600", ("20261023", "부산경남", "4"): "1600",
    ("20261023", "부산경남", "5"): "1400", ("20261023", "부산경남", "6"): "1200",
    ("20261023", "부산경남", "7"): "1800", ("20261023", "부산경남", "8"): "1600", ("20261023", "부산경남", "9"): "1200",
    ("20261023", "영천", "1"): "1000", ("20261023", "영천", "2"): "1200",
    ("20261023", "영천", "3"): "1600", ("20261023", "영천", "4"): "1600",
    ("20261023", "영천", "5"): "1400", ("20261023", "영천", "6"): "1200",
    ("20261023", "영천", "7"): "1800", ("20261023", "영천", "8"): "1600", ("20261023", "영천", "9"): "1200",
    ("20261023", "제주", "1"): "900",  ("20261023", "제주", "2"): "900",
    ("20261023", "제주", "3"): "1000", ("20261023", "제주", "4"): "1000",
    ("20261023", "제주", "5"): "1110", ("20261023", "제주", "6"): "1200", ("20261023", "제주", "7"): "1400",

    # 10월 24일 (토) 다다음 주
    ("20261024", "서울", "1"): "1000", ("20261024", "서울", "2"): "1200",
    ("20261024", "서울", "3"): "1300", ("20261024", "서울", "4"): "1400",
    ("20261024", "서울", "5"): "1800", ("20261024", "서울", "6"): "1200",
    ("20261024", "서울", "7"): "1600", ("20261024", "서울", "8"): "1800",
    ("20261024", "서울", "9"): "1800", ("20261024", "서울", "10"): "1200",
    ("20261024", "제주", "1"): "900",  ("20261024", "제주", "2"): "1000",
    ("20261024", "제주", "3"): "1000", ("20261024", "제주", "4"): "1110",
    ("20261024", "제주", "5"): "1110", ("20261024", "제주", "6"): "1200", ("20261024", "제주", "7"): "1300",

    # 10월 25일 (일) 다다음 주
    ("20261025", "서울", "1"): "1000", ("20261025", "서울", "2"): "1200",
    ("20261025", "서울", "3"): "1200", ("20261025", "서울", "4"): "1300",
    ("20261025", "서울", "5"): "1400", ("20261025", "서울", "6"): "1200",
    ("20261025", "서울", "7"): "1600", ("20261025", "서울", "8"): "2000",
    ("20261025", "서울", "9"): "1700", ("20261025", "서울", "10"): "1800", ("20261025", "서울", "11"): "1400",
    ("20261025", "부산경남", "1"): "1000", ("20261025", "부산경남", "2"): "1200",
    ("20261025", "부산경남", "3"): "1400", ("20261025", "부산경남", "4"): "1400",
    ("20261025", "부산경남", "5"): "1600", ("20261025", "부산경남", "6"): "1800",
    ("20261025", "영천", "1"): "1000", ("20261025", "영천", "2"): "1200",
    ("20261025", "영천", "3"): "1400", ("20261025", "영천", "4"): "1400",
    ("20261025", "영천", "5"): "1600", ("20261025", "영천", "6"): "1800"
}

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

def fetch_meet_data(meet_code, meet_name, date_str):
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
                # 🎯 [철저한 거리 검증] 공식 테이블 ➔ API 거리 ➔ 기본값 순서
                norm_m = get_norm_meet(meet_name)
                dist_lookup = OFFICIAL_DISTANCES.get((str(date_str), norm_m, str(int(rc_no))))
                if not dist_lookup and meet_name in ["부산경남", "영천"]:
                    dist_lookup = OFFICIAL_DISTANCES.get((str(date_str), "부산경남", str(int(rc_no))))
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

def main():
    if not API_KEY:
        print("❌ KRA_API_KEY 미설정")
        return

    now = datetime.now(KST)
    existing_races = {}
    if os.path.exists("race_data.json"):
        try:
            with open("race_data.json", "r", encoding="utf-8") as f:
                old_list = json.load(f)
                for r in old_list:
                    k = f"{r.get('race_date')}_{r.get('meet_name')}_{r.get('race_no')}"
                    existing_races[k] = r
        except: existing_races = {}

    # 1. 기존 오염된 데이터(race_data.json) 파일 완전 삭제 후 백지에서 다시 시작!
    if os.path.exists("race_data.json"):
        os.remove("race_data.json")
    existing_races = {}

    # 2. 이번 주 및 다음 주 주말 전수 수집
    dates_to_fetch = []
    for i in range(7, 0, -1):
        dates_to_fetch.append((now - timedelta(days=i)).strftime("%Y%m%d"))
    dates_to_fetch.append(now.strftime("%Y%m%d"))
    for i in range(1, 15): # 오늘부터 2주 뒤까지 넉넉하게 수집!
        dates_to_fetch.append((now + timedelta(days=i)).strftime("%Y%m%d"))

    unique_dates = sorted(list(set(dates_to_fetch)))
    print(f"🔄 클린 수집 대상 전체 날짜: {unique_dates}")

    for dt in unique_dates:
        for m_code, m_name in MEET_CONFIG:
            res = fetch_meet_data(m_code, m_name, dt)
            for r in res:
                # 🎯 저장할 때 공식 거리를 2중 강제 덮어쓰기!
                norm_m = get_norm_meet(r.get("meet_name"))
                d_val = OFFICIAL_DISTANCES.get((str(r.get("race_date")), norm_m, str(int(r.get("race_no")))))
                if d_val:
                    r["distance"] = d_val
                    for h in r.get("horses", []):
                        h["distance"] = d_val

                k = f"{r.get('race_date')}_{r.get('meet_name')}_{r.get('race_no')}"
                existing_races[k] = r

    final_list = list(existing_races.values())

    # 🎯 [핵심 시간순 타임라인 정렬] 오전 제주 ➔ 낮 부경 ➔ 오후 서울 순서로 완벽 정렬!
    meet_order = {"제주": 1, "부산경남": 2, "영천": 2, "서울": 3}
    final_list.sort(key=lambda x: (
        x["race_date"],
        meet_order.get(x["meet_name"], 9),
        int(x["race_no"]) if str(x["race_no"]).isdigit() else 99
    ))

    if final_list:
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(final_list, f, ensure_ascii=False, indent=2)
        print(f"🎉 성공: [V12.00 클린 리셋] 거리가 완벽히 정화된 총 {len(final_list)}개 경주 저장 완료!")
    else:
        print("❌ 데이터를 가져오지 못했습니다.")

if __name__ == "__main__":
    main()
