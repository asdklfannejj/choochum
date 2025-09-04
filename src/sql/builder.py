
from typing import List, Tuple, Any
from src.dsl.schema import QueryDSL, Filter

def to_sql(dsl: QueryDSL) -> Tuple[str, List[Any]]:
    where_clauses, params = [], []
    for f in dsl.filters:
        if f.op == "IN":
            where_clauses.append(f"u.{f.field} = ANY(%s)")
            params.append(list(f.value))
        else:
            where_clauses.append(f"u.{f.field} {f.op} %s")
            params.append(f.value)

    join_sql = ''
    group_by = 'GROUP BY u.user_id, u.segment'
    if dsl.joins:
        # v0: 단일 조인 가정
        join_sql = ' JOIN transactions tx ON u.user_id = tx.user_id'
        # 실제 파라미터 바인딩/aggregation/having은 단순화 (미리보기 용도)
    base = 'SELECT u.user_id, u.segment FROM users u'
    sql = f"""{base}{join_sql}
WHERE {' AND '.join(where_clauses) if where_clauses else 'TRUE'}
{group_by}"""
    return sql, params
