import os
import requests
from datetime import datetime, timedelta
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
QOO10_23Y_KEY = os.environ["QOO10_23Y_KEY"]
QOO10_OWM_KEY = os.environ["QOO10_OWM_KEY"]

QOO10_API = "https://api.qoo10.jp/GMKT.INC.Front.BizAPI/Giosis.svc/sOpen/json"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_num(v):
    try: return float(str(v).replace(',','').strip())
    except: return None

def parse_int(v):
    n = parse_num(v)
    return int(n) if n is not None else None

def qoo10_get(api_key, method, extra={}):
    params = {"v":"1.0","method":method,"key":api_key,"returnType":"json"}
    params.update(extra)
    r = requests.get(QOO10_API, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_qoo10(api_key, date_str):
    rows = []
    page = 1
    while True:
        data = qoo10_get(api_key, "ShippingBasic.GetShippingInfoListEx", {
            "start_date": date_str,
            "end_date":   date_str,
            "search_type":"1",
            "page_no":    str(page),
            "page_size":  "100",
        })
        result = data.get("ResultObject", [])
        if not result: break
        rows.extend(result)
        if len(result) < 100: break
        page += 1
    return rows

def transform_qoo10(row, yy, mm, dd, reason="주문"):
    return {
        "yy":           yy,
        "mm":           mm,
        "dd":           dd,
        "order_date":   f"{yy:04d}-{mm:02d}-{dd:02d}",
        "reason":       reason,
        "order_no":     str(row.get("order_no") or row.get("ORDER_NO","")).strip(),
        "sales":        parse_num(row.get("settlement_price") or row.get("goods_price") or row.get("GOODS_PRICE")),
        "fee":          parse_num(row.get("fees") or row.get("FEES")),
        "qty":          parse_int(row.get("ord_qty") or row.get("ORD_QTY") or 1),
        "sku":          str(row.get("seller_code") or row.get("SELLER_CODE","")).strip(),
        "product_name": str(row.get("goods_name") or row.get("GOODS_NAME",""))[:100],
        "ad_source":    str(row.get("ad_type") or row.get("AD_TYPE") or "").strip() or None,
    }

def collect(table, api_key, target_date):
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    yy, mm, dd = dt.year, dt.month, dt.day
    date_str = dt.strftime("%Y%m%d")

    print(f"[{table}] {target_date} 수집 중...")
    try:
        raw = fetch_qoo10(api_key, date_str)
    except Exception as e:
        print(f"  API 실패: {e}")
        return

    if not raw:
        print(f"  데이터 없음")
        return

    rows = [transform_qoo10(r, yy, mm, dd) for r in raw]
    supabase.table(table).delete().eq("yy",yy).eq("mm",mm).eq("dd",dd).execute()
    for i in range(0, len(rows), 500):
        supabase.table(table).insert(rows[i:i+500]).execute()
    print(f"  완료: {len(rows)}건")

if __name__ == "__main__":
    target = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"수집 날짜: {target}")
    collect("qoo10_23y", QOO10_23Y_KEY, target)
    collect("qoo10_owm", QOO10_OWM_KEY, target)
    print("전체 완료")
