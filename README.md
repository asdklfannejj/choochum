
# choochum – 가중치 추첨 + 자연어 필터 데모

이 레포는 **자연어 → DSL(JSON) → SQL(미리보기) → 가중치 추첨**의 최소 동작 예시입니다.  
DB 없이 **동봉된 샘플 CSV 데이터**로 바로 실행되며, Streamlit UI를 통해 동작을 확인할 수 있습니다.

## 빠른 시작
```bash
# (선택) 가상환경
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 실행
streamlit run app.py
```

## 폴더 구조
```
choochum/
├── app.py
├── requirements.txt
├── README.md
├── configs/
│   └── schema_whitelist.yml
├── data/
│   ├── users.csv
│   └── transactions.csv
├── src/
│   ├── __init__.py
│   ├── nlp/
│   │   ├── __init__.py
│   │   ├── parser.py
│   │   └── synonyms_ko.yml
│   ├── dsl/
│   │   ├── __init__.py
│   │   └── schema.py
│   ├── sql/
│   │   ├── __init__.py
│   │   └── builder.py
│   ├── draw/
│   │   ├── __init__.py
│   │   └── sampler.py
│   └── audit/
│       ├── __init__.py
│       └── logger.py
└── tests/
    ├── test_parser.py
    ├── test_builder.py
    └── test_sampler.py
```

## 사용 방법 (UI)
1. 왼쪽 사이드바에 **자연어 조건**을 입력합니다.  
   예: `서울/경기 거주, 최근 30일 거래액 10만원 이상, 임직원/테스트 제외`
2. **조건 해석** 버튼을 눌러 DSL과 SQL 미리보기를 확인합니다.
3. 후보군 미리보기를 확인한 후, **당첨자 수**와 **seed(선택)**을 지정하고 **추첨**을 실행합니다.
4. 결과를 CSV로 다운로드할 수 있습니다.

> 참고: SQL은 **미리보기 전용**입니다. 실제 후보군 계산은 동봉된 CSV를 Pandas로 필터링합니다.
