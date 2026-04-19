import os
import json
import gspread
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
# 시트 목록
# ============================================================
SHEETS = [
    # 큐텐 23Y (분기별 4개)
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "1Q",
     "url": "https://docs.google.com/spreadsheets/d/14-EG7ckGOyDDBFdZxTlaWaVEJyXTovUhQXZrgzDeE5g/edit", "tab": "Raw"},
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "2Q",
     "url": "https://docs.google.com/spreadsheets/d/1YR2NZu9uRv9TLZHynl-FTkEcnqdguqcnVrP5o5nU1lI/edit", "tab": "Raw"},
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "3Q",
     "url": "https://docs.google.com/spreadsheets/d/1mODnIP5qKPwfXPilCuUfHwVP1ztvnQ2gMH_O4-6nvYU/edit", "tab": "Raw"},
    {"table": "qoo10_23y", "platform": "qoo10_23y", "quarter": "4Q",
     "url": "https://docs.google.com/spreadsheets/d/1l31uprUNXkwjf5qhiFs4bbDVrpz6eWfS-MN5pVilXkE/edit", "tab": "Raw"},
    # 큐텐 OWM
    {"table": "qoo10_owm", "platform": "qoo10_23y", "quarter": None,
     "url": "https://docs.google.com/spreadsheets/d/160rQSdo5zV6B1Q_X4qeNKQhzxm1uUrzMeXUou_plh2g/edit", "tab": "Raw"},
    # 아마존 JP
    {"table": "amazon", "platform": "amazon", "quarter": None,
     "url": "https://docs.google.com/spreadsheets/d/1n3CYEUpwwASWgijGONz9eN4-kdfW_58U2VGZ3w3cW3E/edit", "tab": "Raw"},
    # 라쿠텐
    {"table": "rakuten", "platform": "rakuten", "quarter": None,
     "url": "https://docs.google.com/spreadsheets/d/1b6orD6pvenMc3cdN2q3kzGIO0INOsAq8L3zNePqyU_s/edit", "tab": "Raw"},
]

# ============================================================
# 유틸
# ============================================================
def pn(v):
    try: return float(str(v).replace(",", "").replace("¥", "").strip())
    except: return None

def pi(v):
    n = pn(v)
    return int(n) if n is not None else None

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
        "yy":           yy,
        "mm":           mm,
        "dd":           dd,
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
    # A열 헤더가 없어서 빈 문자열 키로 저장됨
    yy = pi(row.get("") or row.get("YY") or row.get(" "))
    mm = pi(row.get("MM"))
    dd = pi(row.get("DD"))
    if not yy or not mm or not dd:
        return None
    status = str(row.get("order-status", "") or "").strip()
    if not status:
        return None
    return {
        "yy":           yy,
        "mm":           mm,
        "dd":           dd,
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
    status = str(row.get("상태", "") or "").strip()
    if not status:
        return None
    return {
        "yy":           yy,
        "mm":           mm,
        "dd":           dd,
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
# 시트 처리
# ============================================================
def process_sheet(cfg):
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
# 메인
# ============================================================
if __name__ == "__main__":
    print("구글 시트 → Supabase 동기화 시작\n")
    total = sum(process_sheet(s) for s in SHEETS)
    print(f"\n전체 완료: {total}건")
