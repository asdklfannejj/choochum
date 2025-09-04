
import os, sys, json, re
from datetime import date
from dateutil.relativedelta import relativedelta

import pandas as pd
import streamlit as st

# ---------- Utilities ----------

def simple_number_from_text(txt: str):
    # 10만원, 100000원, 1,234,567 같은 숫자 파싱
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)(\s*(만)?\s*원)?", txt)
    if not m: 
        return None
    num = int(m.group(1).replace(',', ''))
    if m.group(3):  # '만' 존재
        num *= 10000
    return num

def extract_recent_days(txt: str):
    m = re.search(r"최근\s*(\d+)\s*일", txt)
    return int(m.group(1)) if m else None

def normalize_str(s: str):
    return re.sub(r"\s+|_+", "", str(s).lower())

def guess_bool_series(s: pd.Series):
    # 다양한 표현을 True/False로 변환
    true_vals = {"1","y","yes","true","t","예","참","true","Y","True"}
    false_vals = {"0","n","no","false","f","아니오","거짓","N","False"}
    def _to_bool(v):
        if isinstance(v, bool): return v
        sv = str(v).strip()
        if sv in true_vals: return True
        if sv in false_vals: return False
        return None
    return s.map(_to_bool)

def weighted_sample(ids, weights, k, seed=None):
    # 간단한 비복원 가중 샘플 (작은 데이터 기준)
    import random
    rng = random.Random(seed) if seed is not None else random.Random()
    total = sum(weights) if weights else 0
    cand = list(zip(ids, weights))
    chosen = []
    cand = [(i, max(0.0, w)) for i,w in cand]
    while cand and len(chosen) < k:
        total = sum(w for _,w in cand)
        if total <= 0:
            # 균등
            idx = rng.randrange(len(cand))
            chosen.append(cand.pop(idx)[0])
            continue
        r = rng.random() * total
        s = 0.0
        for j,(i,w) in enumerate(cand):
            s += w
            if s >= r:
                chosen.append(i)
                cand.pop(j)
                break
    return chosen

def filter_dataframe(df: pd.DataFrame, nl: str, user_opts):
    cand = df.copy()
    txt = nl or ''

    # 1) 임직원/테스트 제외 (칼럼 추정)
    if any(k in txt for k in ["임직원 제외","직원 제외","사원 제외"]):
        # employee-like column guess
        emp_cols = [c for c in df.columns if any(k in normalize_str(c) for k in ["employee","임직원","직원"])]
        if emp_cols:
            s = guess_bool_series(df[emp_cols[0]])
            cand = cand[(s==False) | (s.isna())]

    if any(k in txt for k in ["테스트 제외","테스트계정 제외","QA 제외"]):
        test_cols = [c for c in df.columns if any(k in normalize_str(c) for k in ["test","테스트"])]
        if test_cols:
            s = guess_bool_series(df[test_cols[0]])
            cand = cand[(s==False) | (s.isna())]

    # 2) 최근 N일 (날짜 칼럼 선택)
    ndays = extract_recent_days(txt)
    dt_col = user_opts.get('date_col')
    if ndays and dt_col and dt_col in cand.columns:
        since = (pd.Timestamp.today().normalize() - pd.Timedelta(days=int(ndays)))
        cand = cand[pd.to_datetime(cand[dt_col], errors='coerce') >= since]

    # 3) 지역/카테고리 (텍스트 토큰이 값에 포함되면 매칭) - 지정된 카테고리 칼럼 대상
    cat_col = user_opts.get('category_col')
    if cat_col and cat_col in cand.columns:
        # 수많은 단어 중 '서울','경기','부산','인천','대구','대전','광주' 등 기본 토큰을 찾음
        tokens = re.findall(r"[가-힣A-Za-z0-9]+", txt)
        targets = set([t for t in tokens if t in ["서울","경기","부산","인천","대구","대전","광주"]])
        if targets:
            cand = cand[cand[cat_col].astype(str).isin(targets)]

    # 4) 숫자 조건: "<컬럼명 유사어> N(만원) 이상/이하/초과/미만"
    num_col = user_opts.get('numeric_col')
    if num_col and num_col in cand.columns:
        num = simple_number_from_text(txt)
        if num is not None:
            if "이상" in txt or "크거나 같" in txt:
                cand = cand[pd.to_numeric(cand[num_col], errors='coerce') >= num]
            elif "이하" in txt or "작거나 같" in txt:
                cand = cand[pd.to_numeric(cand[num_col], errors='coerce') <= num]
            elif "초과" in txt:
                cand = cand[pd.to_numeric(cand[num_col], errors='coerce') > num]
            elif "미만" in txt:
                cand = cand[pd.to_numeric(cand[num_col], errors='coerce') < num]

    return cand

st.set_page_config(page_title='Choochum – 업로드 기반 추첨', layout='wide')
st.title('📥 업로드한 엑셀/CSV에서 자연어 조건으로 가중치 추첨')

with st.sidebar:
    st.header('1) 파일 업로드')
    up = st.file_uploader('엑셀(.xlsx) 또는 CSV', type=['xlsx','csv'])

    st.header('2) 기본 설정')
    id_col = st.text_input('ID 칼럼명 (필수)', value='user_id')
    weight_col = st.text_input('Weight 칼럼명 (선택, 없으면 균등)', value='')

    st.header('3) 조건 해석 보조(선택)')
    date_col = st.text_input('날짜 칼럼명 (예: txn_dt, created_at)', value='')
    category_col = st.text_input('카테고리/지역 칼럼명 (예: region)', value='')
    numeric_col = st.text_input('숫자 조건 칼럼명 (예: amount, score)', value='')

    st.header('4) 자연어 조건')
    nl_text = st.text_area('예: 서울/경기, 최근 30일, 임직원 제외; 거래액 10만원 이상', height=120)

    st.header('5) 추첨 설정')
    k = st.number_input('당첨자 수', value=10, min_value=1, max_value=100000)
    seed_in = st.text_input('seed (선택, 숫자)', placeholder='예: 42 (비워두면 매번 랜덤)', help='seed는 난수의 시작값입니다. 같은 후보군+같은 seed면 결과가 동일하게 재현됩니다.')

if up is not None:
    # Load
    if up.name.lower().endswith('.xlsx'):
        df = pd.read_excel(up)
    else:
        df = pd.read_csv(up)
    st.subheader('업로드 미리보기')
    st.write(f'행: {len(df)}, 열: {len(df.columns)}')
    st.dataframe(df.head(20))

    # Show detected columns
    st.caption('칼럼 예시: ' + ', '.join(map(str, df.columns[:10])) + (' ...' if len(df.columns) > 10 else ''))

    # Buttons
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('조건 해석 & 후보군 보기'):
            if id_col not in df.columns:
                st.error(f'ID 칼럼 "{id_col}" 을(를) 찾을 수 없습니다. 실제 칼럼명을 확인해 주세요.')
            else:
                cand = filter_dataframe(df, nl_text, {
                    'date_col': date_col if date_col in df.columns else None,
                    'category_col': category_col if category_col in df.columns else None,
                    'numeric_col': numeric_col if numeric_col in df.columns else None,
                })
                st.session_state['cand_df'] = cand
                st.session_state['id_col'] = id_col
                st.session_state['weight_col'] = (weight_col if weight_col in df.columns else None)

                st.write(f'후보군 수: {len(cand)}')
                preview_cols = [c for c in [id_col, weight_col, category_col, numeric_col, date_col] if c in cand.columns]
                if not preview_cols:
                    preview_cols = list(cand.columns)[:6]
                st.dataframe(cand[preview_cols].head(200))

    with col_b:
        if st.button('추첨'):
            cand = st.session_state.get('cand_df')
            if cand is None or cand.empty:
                st.warning('먼저 "조건 해석 & 후보군 보기"를 눌러 후보군을 생성하세요.')
            else:
                idc = st.session_state.get('id_col')
                wc = st.session_state.get('weight_col')
                ids = cand[idc].astype(str).tolist()
                weights = (pd.to_numeric(cand[wc], errors='coerce').fillna(1.0).tolist() if wc else [1.0]*len(cand))
                seed_val = int(seed_in) if seed_in.strip().isdigit() else None
                winners = weighted_sample(ids, weights, int(k), seed=seed_val)
                out = pd.DataFrame({idc: winners})
                st.subheader('당첨자')
                st.dataframe(out)
                st.download_button('CSV 다운로드', data=out.to_csv(index=False).encode('utf-8-sig'),
                                   file_name='winners.csv', mime='text/csv')

    # 메인 영역 하단에 '추첨 실행' 버튼을 항상 제공 (후보군 미생성 시 즉시 생성 후 진행)
    st.markdown('---')
    st.subheader('🎯 추첨 실행')
    st.caption('먼저 위에서 조건을 해석해 후보군을 확인하는 것을 권장하지만, 바로 추첨도 가능합니다.')

    if st.button('🎯 추첨 실행 (바로 진행)'):
        # seed 유효성 검사
        if seed_in.strip() and not seed_in.strip().isdigit():
            st.error('seed는 숫자만 입력하세요. 예: 42  (비우면 매 실행마다 다른 결과입니다)')
        else:
            # 후보군 준비
            cand = st.session_state.get('cand_df')
            if cand is None:
                # 즉시 필터링 시도
                if id_col not in df.columns:
                    st.error(f'ID 칼럼 "{id_col}" 을(를) 찾을 수 없습니다. 먼저 올바른 ID 칼럼명을 입력하세요.')
                else:
                    cand = filter_dataframe(df, nl_text, {
                        'date_col': date_col if date_col in df.columns else None,
                        'category_col': category_col if category_col in df.columns else None,
                        'numeric_col': numeric_col if numeric_col in df.columns else None,
                    })
            if cand is not None and not cand.empty:
                idc = id_col
                wc = (weight_col if weight_col in df.columns else None)
                ids = cand[idc].astype(str).tolist()
                weights = (pd.to_numeric(cand[wc], errors='coerce').fillna(1.0).tolist() if wc else [1.0]*len(cand))
                seed_val = int(seed_in) if seed_in.strip().isdigit() else None
                winners = weighted_sample(ids, weights, int(k), seed=seed_val)
                out = pd.DataFrame({idc: winners})
                st.success(f'추첨 완료! (후보군 {len(cand)}명, 당첨 {len(out)}명)')
                st.dataframe(out)
                st.download_button('CSV 다운로드', data=out.to_csv(index=False).encode('utf-8-sig'),
                                   file_name='winners.csv', mime='text/csv')
            elif cand is not None and cand.empty:
                st.warning('후보군이 비어 있습니다. 조건을 완화하거나 칼럼명을 확인하세요.')
else:
    st.info('좌측에서 엑셀(.xlsx) 또는 CSV를 업로드하세요.')
