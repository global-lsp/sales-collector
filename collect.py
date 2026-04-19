import os
import json
import gspread
import requests as req
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SA_JSON      = os.environ["GOOGLE_SERVICE_ACCOUNT"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

creds = Credentials.from_service_account_info(
    json.loads(SA_JSON),
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(creds)

# ============================================================
# 시트 목록 - 매출 Raw
# ============================================================
SALES_SHEETS = [
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "1Q",
     "url": "https://docs.google.com/spreadsheets/d/14-EG7ckGOyDDBFdZxTlaWaVEJyXTovUhQXZrgzDeE5g/edit", "tab": "Raw"},
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "2Q",
     "url": "https://docs.google.com/spreadsheets/d/1YR2NZu9uRv9TLZHynl-FTkEcnqdguqcnVrP5o5nU1lI/edit", "tab": "Raw"},
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "3Q",
     "url": "https://docs.google.com/spreadsheets/d/1mODnIP5qKPwfXPilCuUfHwVP1ztvnQ2gMH_O4-6nvYU/edit", "tab": "Raw"},
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "4Q",
     "url": "https://docs.google.com/spreadsheets/d/1l31uprUNXkwjf5qhiFs4bbDVrpz6eWfS-MN5pVilXkE/edit", "tab": "Raw"},
    {"table": "qoo10_owm", "platform": "qoo10_23y", "quarter": None,
     "url": "https://docs.google.com/spreadsheets/d/160rQSdo5zV6B1Q_X4qeNKQhzxm1uUrzMeXUou_plh2g/edit", "tab": "Raw"},
    {"table": "amazon", "platform": "amazon", "quarter": None,
     "url": "https://docs.google.com/spreadsheets/d/1n3CYEUpwwASWgijGONz9eN4-kdfW_58U2VGZ3w3cW3E/edit", "tab": "Raw"},
    {"table": "rakuten", "platform": "rakuten", "quarter": None,
     "url": "https://docs.google.com/spreadsheets/d/1b6orD6pvenMc3cdN2q3kzGIO0INOsAq8L3zNePqyU_s/edit", "tab": "Raw"},
]

# ============================================================
# 광고비 시트 목록
# ============================================================
AD_SHEETS = [
    {"table": "ad_amazon", "platform": "amazon",
     "url": "https://docs.google.com/spreadsheets/d/1n3CYEUpwwASWgijGONz9eN4-kdfW_58U2VGZ3w3cW3E/edit", "tab": "광고"},
    {"table": "ad_qoo10_23y", "platform": "qoo10_23y",
     "url": "https://docs.google.com/spreadsheets/d/14-EG7ckGOyDDBFdZxTlaWaVEJyXTovUhQXZrgzDeE5g/edit", "tab": "광고비"},
    {"table": "ad_qoo10_23y", "platform": "qoo10_23y",
     "url": "https://docs.google.com/spreadsheets/d/1YR2NZu9uRv9TLZHynl-FTkEcnqdguqcnVrP5o5nU1lI/edit", "tab": "광고비"},
    {"table": "ad_rakuten", "platform": "rakuten",
     "url": "https://docs.google.com/spreadsheets/d/1b6orD6pvenMc3cdN2q3kzGIO0INOsAq8L3zNePqyU_s/edit", "tab": "광고비"},
]

# ============================================================
# 유틸
# ============================================================
def pn(v):
    try: return float(str(v).replace(",", "").replace("¥", "").replace("₩", "").strip())
    except: return None

def pi(v):
    n = pn(v)
    return int(n) if n is not None else None

# ============================================================
# 환율 가져오기 (ExchangeRate-API 무료)
# ============================================================
def get_exchange_rate(date_str):
    """JPY → KRW 환율 가져오기"""
    try:
        r = req.get(f"https://api.exchangerate-api.com/v4/latest/JPY", timeout=10)
        data = r.json()
        rate = data.get("rates", {}).get("KRW", 9.4)
        print(f"  환율 JPY→KRW: {rate:.2f}")
        return round(rate, 4)
    except Exception as e:
        print(f"  환율 API 실패 ({e}), 기본값 9.4 사용")
        return 9.4

# ============================================================
# 변환 함수
# ============================================================
def transform_qoo10(row):
    yy = pi(row.get("YY"))
    mm = pi(row.get("MM"))
    dd = pi(row.get("DD"))
    if not yy or not mm or not dd:
        return None
    reason = str(row.get("발생사유", "")).strip()
    if reason not in ("주문", "취소"):
        return None
    return {
        "yy": yy, "mm": mm, "dd": dd,
        "order_date":   f"{yy:04d}-{mm:02d}-{dd:02d}",
        "reason":       reason,
        "order_no":     str(row.get("주문번호", "") or ""),
        "sales":        pn(row.get("상품결제금")),
        "fee":          pn(row.get("Qoo10서비스수수료")),
        "qty":          pi(row.get("수량") or 1),
        "sku":          str(row.get("판매자코드", "") or ""),
        "product_name": str(row.get("상품명", "") or "")[:100],
        "ad_source":    str(row.get("외부광고", "") or "") or None,
    }

def transform_amazon(row):
    yy = pi(row.get("") or row.get("YY") or row.get(" "))
    mm = pi(row.get("MM"))
    dd = pi(row.get("DD"))
    if not yy or not mm or not dd:
        return None
    status = str(row.get("order-status", "") or "").strip()
    if not status:
        return None
    return {
        "yy": yy, "mm": mm, "dd": dd,
        "order_date":   f"{yy:04d}-{mm:02d}-{dd:02d}",
        "order_status": status,
        "order_id":     str(row.get("amazon-order-id", "") or ""),
        "sales":        pn(row.get("item-price")) if status != "Cancelled" else 0,
        "qty":          pi(row.get("quantity") or 1),
        "sku":          str(row.get("sku", "") or ""),
        "product_name": str(row.get("product-name", "") or "")[:100],
        "fba":          pn(row.get("FBA")),
        "krjp":         pn(row.get("KR-JP")),
        "label_cost":   pn(row.get("라벨비용")),
        "import_tax":   pn(row.get("수입소비세")),
    }

def transform_rakuten(row):
    yy = pi(row.get("YY"))
    mm = pi(row.get("MM"))
    dd = pi(row.get("DD"))
    if not yy or not mm or not dd:
        return None
    # 상태값이 숫자로 올 수 있어서 int 변환 후 str
    raw_status = row.get("상태")
    if raw_status is None or str(raw_status).strip() == "":
        return None
    try:
        status = str(int(float(str(raw_status).strip())))
    except:
        status = str(raw_status).strip()
    return {
        "yy": yy, "mm": mm, "dd": dd,
        "order_date":   f"{yy:04d}-{mm:02d}-{dd:02d}",
        "status":       status,
        "order_no":     str(row.get("주문번호", "") or ""),
        "sales":        pn(row.get("총 결제금액")),
        "qty":          pi(row.get("갯수") or 1),
        "sku":          str(row.get("시스템 연계용 SKu 번호", "") or row.get("상품코드", "") or ""),
        "product_name": str(row.get("상품명", "") or "")[:100],
        "cogs":         pn(row.get("원가(엔)")),
        "shipping":     pn(row.get("배송비")),
    }

TRANSFORMERS = {
    "qoo10_23y": transform_qoo10,
    "amazon":    transform_amazon,
    "rakuten":   transform_rakuten,
}

# ============================================================
# 광고비 변환
# ============================================================
def transform_ad_amazon(row):
    yy = pi(row.get("YY"))
    mm = pi(row.get("MM"))
    dd = pi(row.get("DD"))
    if not yy or not mm or not dd:
        return None
    total = pn(row.get("TOTAL"))
    if not total:
        return None
    return {
        "yy": yy, "mm": mm, "dd": dd,
        "order_date": f"{yy:04d}-{mm:02d}-{dd:02d}",
        "platform":   "amazon",
        "sp":         pn(row.get("SP")),
        "sb":         pn(row.get("SB")),
        "sd":         pn(row.get("SD")),
        "dsp":        pn(row.get("DSP")),
        "influencer": pn(row.get("인플루언서")),
        "total_jpy":  total,
        "currency":   "JPY",
    }

def transform_ad_qoo10(row):
    yy = pi(row.get("YY"))
    mm = pi(row.get("MM"))
    dd = pi(row.get("DD"))
    if not yy or not mm or not dd:
        return None
    total = pn(row.get("TOTAL"))
    if not total:
        return None
    return {
        "yy": yy, "mm": mm, "dd": dd,
        "order_date": f"{yy:04d}-{mm:02d}-{dd:02d}",
        "platform":   "qoo10_23y",
        "keyword":    pn(row.get("Qoo10 Keyword") or row.get("Qoo10 Keywor")),
        "influencer": pn(row.get("인플루언서")),
        "meta":       pn(row.get("Meta(Branded") or row.get("Meta(Brande")),
        "total_krw":  total,
        "currency":   "KRW",
    }

def transform_ad_rakuten(row):
    yy = pi(row.get("YY"))
    mm = pi(row.get("MM"))
    dd = pi(row.get("DD"))
    if not yy or not mm or not dd:
        return None
    total = pn(row.get("TOTAL"))
    if not total:
        return None
    return {
        "yy": yy, "mm": mm, "dd": dd,
        "order_date": f"{yy:04d}-{mm:02d}-{dd:02d}",
        "platform":   "rakuten",
        "rpp":        pn(row.get("검색(RPP)")),
        "cpa":        pn(row.get("효과보증형(CPA)")),
        "tda":        pn(row.get("배너(TDA)")),
        "influencer": pn(row.get("인플루언서")),
        "meta":       pn(row.get("Meta(Branded)")),
        "total_krw":  total,
        "currency":   "KRW",
    }

# ============================================================
# 시트 처리 - 매출
# ============================================================
def process_sales_sheet(cfg):
    table    = cfg["table"]
    platform = cfg["platform"]
    url      = cfg["url"]
    tab      = cfg["tab"]
    quarter  = cfg.get("quarter") or ""
    label    = f"{table} {quarter}".strip()

    print(f"\n[{label}] 읽는 중...")
    try:
        sh      = gc.open_by_url(url)
        ws      = sh.worksheet(tab)
        records = ws.get_all_records()
        print(f"  읽은 행수: {len(records)}")
    except Exception as e:
        print(f"  시트 읽기 실패: {e}")
        return 0

    transform = TRANSFORMERS[platform]
    rows = [transform(r) for r in records]
    rows = [r for r in rows if r]
    print(f"  변환된 행수: {len(rows)}")
    if not rows:
        return 0

    years  = set(r["yy"] for r in rows)
    months = set(r["mm"] for r in rows)
    for yy in years:
        for mm in months:
            supabase.table(table).delete().eq("yy", yy).eq("mm", mm).execute()

    for i in range(0, len(rows), 500):
        supabase.table(table).insert(rows[i:i+500]).execute()

    print(f"  업로드 완료: {len(rows)}건")
    return len(rows)

# ============================================================
# 시트 처리 - 광고비
# ============================================================
def process_ad_sheet(cfg, exchange_rate):
    table    = cfg["table"]
    platform = cfg["platform"]
    url      = cfg["url"]
    tab      = cfg["tab"]

    print(f"\n[광고비 {platform}] 읽는 중...")
    try:
        sh      = gc.open_by_url(url)
        ws      = sh.worksheet(tab)
        records = ws.get_all_records()
        print(f"  읽은 행수: {len(records)}")
    except Exception as e:
        print(f"  시트 읽기 실패: {e}")
        return 0

    if platform == "amazon":
        rows = [transform_ad_amazon(r) for r in records]
    elif platform == "qoo10_23y":
        rows = [transform_ad_qoo10(r) for r in records]
    elif platform == "rakuten":
        rows = [transform_ad_rakuten(r) for r in records]
    else:
        return 0

    rows = [r for r in rows if r]

    # 환율 적용 - JPY는 실제환율로 KRW 환산, KRW는 그대로
    for r in rows:
        if r.get("currency") == "JPY":
            r["total_krw_actual"] = round((r.get("total_jpy") or 0) * exchange_rate)
            r["total_krw_fixed"]  = round((r.get("total_jpy") or 0) * 9.4)
        else:
            r["total_krw_actual"] = r.get("total_krw")
            r["total_krw_fixed"]  = r.get("total_krw")
        r["exchange_rate_actual"] = exchange_rate
        r["exchange_rate_fixed"]  = 9.4

    print(f"  변환된 행수: {len(rows)}")
    if not rows:
        return 0

    years  = set(r["yy"] for r in rows)
    months = set(r["mm"] for r in rows)
    for yy in years:
        for mm in months:
            supabase.table(table).delete().eq("yy", yy).eq("mm", mm).execute()

    for i in range(0, len(rows), 500):
        supabase.table(table).insert(rows[i:i+500]).execute()

    print(f"  업로드 완료: {len(rows)}건")
    return len(rows)

# ============================================================
# 메인
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("구글 시트 → Supabase 동기화 시작")
    print("=" * 50)

    # 환율 가져오기
    print("\n[환율] 가져오는 중...")
    exchange_rate = get_exchange_rate(datetime.today().strftime("%Y-%m-%d"))

    # 매출 Raw 수집
    print("\n--- 매출 데이터 ---")
    sales_total = sum(process_sales_sheet(s) for s in SALES_SHEETS)

    # 광고비 수집
    print("\n--- 광고비 데이터 ---")
    ad_total = sum(process_ad_sheet(s, exchange_rate) for s in AD_SHEETS)

    print(f"\n{'='*50}")
    print(f"매출 완료: {sales_total}건")
    print(f"광고비 완료: {ad_total}건")
    print(f"{'='*50}")
