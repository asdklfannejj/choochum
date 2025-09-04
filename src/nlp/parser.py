
import re
from datetime import date
from dateutil.relativedelta import relativedelta

from src.dsl.schema import QueryDSL, Filter, Join

def _norm_days(text: str):
    m = re.search(r"최근\s*(\d+)\s*일", text)
    if not m:
        return None
    d = date.today() - relativedelta(days=int(m.group(1)))
    return d.isoformat()

def parse(text: str) -> QueryDSL:
    text = (text or '').strip()
    regions = []
    for key in ["서울","경기","인천","부산","대전","광주","대구"]:
        if key in text:
            regions.append(key)

    filters = []
    if regions:
        filters.append(Filter(field="region", op="IN", value=regions))

    if any(k in text for k in ["임직원 제외","직원 제외","사원 제외"]):
        filters.append(Filter(field="is_employee", op="=", value=False))
    if any(k in text for k in ["테스트 제외","테스트계정 제외","QA 제외"]):
        filters.append(Filter(field="is_test_user", op="=", value=False))

    since = _norm_days(text)
    joins = []
    amt_m = re.search(r"(\d+)\s*만원\s*이상|([0-9]{3,})\s*원\s*이상", text)
    needs_txn = ("거래" in text) or ("거래액" in text) or ("사용금액" in text)
    if needs_txn and since and amt_m:
        amount = int(amt_m.group(1) or amt_m.group(2)) * (10000 if amt_m.group(1) else 1)
        joins.append(Join.model_validate({
            "with": "transactions",
            "on": "users.user_id = transactions.user_id",
            "type": "inner",
            "aggregations": [{
                "field":"amount","fn":"SUM","as":"sum_amount",
                "filters":[{"field":"txn_dt","op":">=","value":since}]
            }],
            "having": [{"field":"sum_amount","op":">=","value":amount}]
        }))

    return QueryDSL(target="users", filters=filters, joins=joins)
