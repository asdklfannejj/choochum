# Weighted Raffle (Streamlit)

가중치 기반 추첨 엔진과 챗봇형 UI.

## 설치
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 실행
```bash
streamlit run app.py
```

기본 경로의 데이터: `/mnt/data/hana_dummy_30000_20250901_084807.xlsx`

## 규칙 예시 (채팅창에 입력)
```
성별: 남성=1.0, 여성=1.1
거주지역: 서울=1.2, 경기=1.1, 기타=1.0
나이: [19-29]=1.05, [30-39]=1.10, [40-49]=1.00, [50-120]=0.95
eligibility: 나이 >= 19
당첨자수=100
seed=42
추첨
```

## 테스트
```bash
pytest -q
```
