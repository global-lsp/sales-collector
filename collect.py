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

    # 응답이 [[주문리스트], [취소리스트]] 구조
    rows = []
    if isinstance(data, list):
        for group in data:
            if isinstance(group, list):
                for item in group:
                    if isinstance(item, list):
                        for row in item:
                            if isinstance(row, dict):
                                rows.append(row)
                    elif isinstance(item, dict):
                        rows.append(item)

    print(f"  파싱된 행수: {len(rows)}")
    if rows:
        print(f"  첫 번째 행 키: {list(rows[0].keys())[:10]}")
    return rows


def pn(v):
    try:
        return float(str(v).replace(",", "").strip())
    except:
        return None


def pi(v):
    n = pn(v)
    return int(n) if n is not None else None


def transform(row, yy, mm, dd):
    return {
        "yy":           yy,
        "mm":           mm,
        "dd":           dd,
        "order_date":   f"{yy:04d}-{mm:02d}-{dd:02d}",
        "reason":       str(row.get("OrderStatus") or row.get("Reason") or row.get("order_status") or "주문"),
        "order_no":     str(row.get("OrderNo") or row.get("PackNo") or row.get("order_no") or ""),
        "sales":        pn(row.get("GoodsPrice") or row.get("SettlementPrice") or row.get("PaymentPrice") or row.get("goods_price")),
        "fee":          pn(row.get("Fees") or row.get("CommissionFee") or row.get("ServiceFee") or row.get("fees")),
        "qty":          pi(row.get("OrderQty") or row.get("Qty") or row.get("order_qty") or 1),
        "sku":          str(row.get("SellerCode") or row.get("SellerItemCode") or row.get("seller_code") or ""),
        "product_name": str(row.get("GoodsName") or row.get("ItemTitle") or row.get("goods_name") or "")[:100],
        "ad_source":    str(row.get("AdType") or row.get("ExternalAd") or row.get("ad_type") or "") or None,
    }


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
    except Exception as e:
        print(f"  조회 실패: {e}")
        return 0

    if not raw:
        print("  데이터 없음 (해당 날짜 판매 없음)")
        return 0

    rows = [transform(r, yy, mm, dd) for r in raw]
    supabase.table(table).delete().eq("yy", yy).eq("mm", mm).eq("dd", dd).execute()
    for i in range(0, len(rows), 500):
        supabase.table(table).insert(rows[i:i+500]).execute()

    print(f"  업로드 완료: {len(rows)}건")
    return len(rows)


if __name__ == "__main__":
    target = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"수집 날짜: {target}")
    total = sum(collect(a, target) for a in ACCOUNTS)
    print(f"\n전체 완료: {total}건")
