
from src.nlp.parser import parse

def test_parse_minimal():
    dsl = parse('서울/경기 거주, 최근 30일 거래액 10만원 이상, 임직원/테스트 제외')
    assert dsl.target == 'users'
    assert any(f.field == 'region' for f in dsl.filters)
