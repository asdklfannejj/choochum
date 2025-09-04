
from src.dsl.schema import QueryDSL, Filter
from src.sql.builder import to_sql

def test_builder_sql():
    dsl = QueryDSL(filters=[Filter(field='region', op='IN', value=['서울','경기'])])
    sql, params = to_sql(dsl)
    assert 'FROM users u' in sql
    assert 'region' in sql and params
