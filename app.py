
import os, sys, json
import pandas as pd
import streamlit as st

# src 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.nlp.parser import parse
from src.sql.builder import to_sql
from src.draw.sampler import sample_unique
from src.audit.logger import snapshot_hash, write_audit

st.set_page_config(page_title='Choochum – 자연어 기반 가중치 추첨', layout='wide')
st.title('🎯 Choochum – 자연어 기반 가중치 추첨 데모')

st.sidebar.header('자연어 조건 입력')
default_text = '서울/경기 거주, 최근 30일 거래액 10만원 이상, 임직원/테스트 제외'
text = st.sidebar.text_area('예시를 참고해 조건을 입력하세요.', value=default_text, height=120)

k = st.number_input('당첨자 수', value=5, min_value=1, max_value=1000)
seed = st.text_input('seed (선택, 숫자)', value='')

if st.sidebar.button('조건 해석'):
    dsl = parse(text)
    sql, params = to_sql(dsl)
    st.subheader('DSL (자연어→JSON)')
    st.code(json.dumps(dsl.model_dump(), ensure_ascii=False, indent=2), language='json')

    st.subheader('SQL 미리보기 (실행 아님)')
    st.code(sql)
    st.caption(f'params: {params}')

    # 샘플 CSV 로드 (실제 운영에선 DB 조회)
    users = pd.read_csv('data/users.csv', dtype={'user_id':str})
    tx = pd.read_csv('data/transactions.csv', dtype={'user_id':str})

    # DSL 기반 후보군 계산 (Pandas)
    cand = users.copy()

    # filters
    for f in dsl.filters:
        if f.op == 'IN':
            cand = cand[cand[f.field].isin(f.value)]
        elif f.op in ['=','!=']:
            cand = cand[cand[f.field]==f.value] if f.op=='=' else cand[cand[f.field]!=f.value]
        # 단순 데모이므로 숫자/날짜 비교는 생략

    # joins/aggregations (v0 간단 구현: 최근 N일 합계 >= amount)
    if dsl.joins:
        j = dsl.joins[0]
        since = None
        amount_min = None
        for agg in (j.aggregations or []):
            for flt in agg.get('filters', []):
                if flt['field']=='txn_dt' and flt['op']=='>=':
                    since = flt['value']
        for hv in (j.having or []):
            if hv.field=='sum_amount' and hv.op=='>=':
                amount_min = hv.value
        if since and amount_min is not None:
            tx2 = tx[tx['txn_dt']>=since]
            sum_tx = tx2.groupby('user_id')['amount'].sum().reset_index().rename(columns={'amount':'sum_amount'})
            cand = cand.merge(sum_tx, on='user_id', how='inner')
            cand = cand[cand['sum_amount']>=amount_min]

    # 가중치 룰 (예: VIP 1.5x, 기타 1.0)
    cand['effective_weight'] = cand['segment'].apply(lambda s: 1.5 if str(s).upper()=='VIP' else 1.0)

    st.subheader('후보군 미리보기')
    st.write(f'후보군 수: {len(cand)} 명')
    st.dataframe(cand[['user_id','name','region','segment','effective_weight']].reset_index(drop=True))

    st.session_state['cand_df'] = cand
    st.session_state['dsl_json'] = dsl.model_dump()
    st.session_state['sql_text'] = sql

if st.button('추첨'):
    cand = st.session_state.get('cand_df')
    if cand is None or cand.empty:
        st.warning('먼저 왼쪽의 **조건 해석** 버튼을 눌러 후보군을 생성하세요.')
    else:
        ids = cand['user_id'].tolist()
        weights = cand['effective_weight'].tolist()
        seed_val = int(seed) if seed.strip().isdigit() else None
        winners = sample_unique(ids, weights, int(k), seed=seed_val)

        st.subheader('당첨자')
        out = pd.DataFrame({'user_id': winners})
        st.dataframe(out)

        # 감사 기록
        shash = snapshot_hash(ids)
        audit_path = write_audit(
            event_id='demo',
            seed=seed_val,
            dsl_json=st.session_state.get('dsl_json', {}),
            sql=st.session_state.get('sql_text', ''),
            snapshot_hash_value=shash,
            outdir='runs'
        )
        st.success(f'감사 로그 생성: {audit_path}')
        st.download_button('CSV 다운로드', data=out.to_csv(index=False).encode('utf-8-sig'),
                           file_name='winners.csv', mime='text/csv')

st.info('이 데모는 CSV + Pandas로 동작합니다. 운영에서는 DB 조회/권한/감사 등을 강화하세요.')
