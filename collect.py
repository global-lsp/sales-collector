import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from supabase import create_client
 
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
 
QOO10_API = "https://api.qoo10.jp/GMKT.INC.Front.QAPIService/ebayjapan.qapi"
 
ACCOUNTS = [
    {
        "table":    "qoo10_23y",
        "user_id":  "23yearsold",
        "password": os.environ["QOO10_23Y_PASS"],
        "api_key":  os.environ["QOO10_23Y_KEY"],
    },
    {
        "table":    "qoo10_owm",
        "user_id":  "owm_official",
        "password": os.environ["QOO10_OWM_PASS"],
        "api_key":  os.environ["QOO10_OWM_KEY"],
    },
]
 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
 
def get_sak(user_id, password, api_key):
    url = f"{QOO10_API}/CertificationAPI.CreateCertificationKey"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "GiosisCertificationKey": api_key,
        "QAPIVersion": "1.0",
    }
    r = requests.post(url, headers=headers, data={
        "returnType": "text/xml",
        "user_id": user_id,
        "pwd": password,
    }, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    msg = root.find("ResultMsg").text
    sak = root.find("ResultObject").text
    print(f"  SAK 발급: {msg}")
    return sak
 
 
def get_selling_report(sak, date_str):
    url = f"{QOO10_API}/ShippingBasic.GetSellingReportDetailList"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "GiosisCertificationKey": sak,
        "QAPIVersion": "1.0",
    }
    r = requests.post(url, headers=headers, data={
        "returnType":      "application/json",
        "SearchStartDate": date_str,
        "SearchEndDate":   date_str,
        "SearchCondition": "2",
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
 
    # 응답 구조 출력 (디버깅용)
    print(f"  응답 타입: {type(data)}")
    if isinstance(data, dict):
        print(f"  응답 키: {list(data.keys())}")
        result = data.get("ResultObject")
        print(f"  ResultObject 타입: {type(result)}")
        if result:
            print(f"  첫 번째 항목 타입: {type(result[0]) if isinstance(result, list) else type(result)}")
            print(f"  첫 번째 항목 미리보기: {str(result[0])[:200] if isinstance(result, list) else str(result)[:200]}")
    elif isinstance(data, list):
        print(f"  리스트 길이: {len(data)}")
        if data:
            print(f"  첫 번째 항목 타입: {type(data[0])}")
            print(f"  첫 번째 항목 미리보기: {str(data[0])[:200]}")
 
    return data
 
 
def collect(account, target_date):
    table = account["table"]
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    yy, mm, dd = dt.year, dt.month, dt.day
    date_str = dt.strftime("%Y%m%d")
 
    print(f"\n[{table}] {target_date} 수집 중...")
 
    try:
        sak = get_sak(account["user_id"], account["password"], account["api_key"])
    except Exception as e:
        print(f"  SAK 발급 실패: {e}")
        return 0
 
    try:
        raw = get_selling_report(sak, date_str)
        print(f"  조회 완료")
    except Exception as e:
        print(f"  조회 실패: {e}")
        return 0
 
    return 0
 
 
if __name__ == "__main__":
    target = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"수집 날짜: {target}")
    # 23y만 먼저 테스트
    collect(ACCOUNTS[0], target)
    print(f"\n디버깅 완료")
