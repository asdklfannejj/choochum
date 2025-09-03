import os
import io
import yaml
import pandas as pd
import streamlit as st
from datetime import datetime
from src.weighted_draw import run_raffle

st.set_page_config(page_title="가중치 추첨 챗봇", page_icon="🎯")

DEFAULT_PATH = "/mnt/data/hana_dummy_30000_20250901_084807.xlsx"

SYSTEM_TIPS = (
    "규칙 입력 예시:\n"
    "• 성별: 남성=1.0, 여성=1.1\n"
    "• 거주지역: 서울=1.2, 경기=1.1, 기타=1.0\n"
    "• 나이: [19-29]=1.05, [30-39]=1.10, [40-49]=1.00, [50-120]=0.95\n"
    "자격조건 추가: `eligibility: 나이 >= 19` 처럼 메시지로 보내주세요.\n"
    "명령: `당첨자수=100`, `seed=42`, `추첨`, `규칙보기`, `규칙초기화`"
)

if "config" not in st.session_state:
    st.session_state.config = {
        "unique_key": "고객ID",
        "eligibility": [],
        "weights": {},
        "defaults": {"categorical": 1.0, "bucket": 1.0}
    }

if "n_winners" not in st.session_state:
    st.session_state.n_winners = 100

if "seed" not in st.session_state:
    st.session_state.seed = 42

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 가중치 기반 추첨을 도와드려요. 파일을 올리거나 기본 파일로 진행하실 수 있어요.\n" + SYSTEM_TIPS}
    ]

st.title("🎯 가중치 추첨 챗봇")

uploaded = st.file_uploader("엑셀 업로드(.xlsx). 미업로드 시 기본 파일을 사용합니다.", type=["xlsx"])
if uploaded:
    df = pd.read_excel(uploaded)
else:
    if os.path.exists(DEFAULT_PATH):
        df = pd.read_excel(DEFAULT_PATH)
        st.caption("기본 데이터 파일을 사용 중입니다.")
    else:
        st.error("데이터 파일이 없습니다. 엑셀을 업로드해주세요.")
        st.stop()

with st.expander("데이터 샘플 보기", expanded=False):
    st.dataframe(df.head(10))

def parse_rule_line(line: str):
    if ":" not in line:
        return None
    col, rhs = [x.strip() for x in line.split(":", 1)]
    items = [x.strip() for x in rhs.split(",") if x.strip()]
    cat_map = {}
    buckets = []
    is_bucket = False
    for it in items:
        if "=" not in it:
            continue
        k, v = [x.strip() for x in it.split("=", 1)]
        try:
            w = float(v)
        except:
            continue
        if k.startswith("[") and k.endswith("]") and "-" in k:
            lo, hi = k[1:-1].split("-", 1)
            lo = float(lo.strip()); hi = float(hi.strip())
            buckets.append([lo, hi, w])
            is_bucket = True
        else:
            cat_map[k] = w
    if is_bucket:
        return col, {"type": "bucket", "buckets": buckets}
    elif cat_map:
        return col, {"type": "categorical", "mapping": cat_map}
    return None

def add_eligibility(expr: str):
    st.session_state.config.setdefault("eligibility", [])
    st.session_state.config["eligibility"].append(expr)

with st.sidebar:
    st.header("설정")
    st.session_state.n_winners = st.number_input("당첨자 수", 1, 100000, st.session_state.n_winners)
    st.session_state.seed = st.number_input("seed (재현성)", 0, 10**9, st.session_state.seed)
    st.text_area("도움말", SYSTEM_TIPS, height=180)

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

user_input = st.chat_input("규칙/명령을 입력하세요")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    reply = ""
    text = user_input.strip()

    if text.lower().startswith("seed="):
        try:
            st.session_state.seed = int(text.split("=",1)[1])
            reply = f"seed를 {st.session_state.seed}로 설정했어요."
        except:
            reply = "seed 설정에 실패했어요. 정수를 입력해주세요."
    elif text.startswith("당첨자수=") or text.startswith("추첨인원="):
        try:
            n = int(text.split("=",1)[1])
            st.session_state.n_winners = n
            reply = f"당첨자 수를 {n}명으로 설정했어요."
        except:
            reply = "당첨자 수 설정에 실패했어요. 정수를 입력해주세요."
    elif text.startswith("eligibility:"):
        expr = text.split(":",1)[1].strip()
        add_eligibility(expr)
        reply = f"자격조건을 추가했어요: `{expr}`"
    elif text == "규칙보기":
        reply = "현재 규칙:\n```\n" + yaml.safe_dump(st.session_state.config, allow_unicode=True, sort_keys=False) + "```"
    elif text == "규칙초기화":
        st.session_state.config = {
            "unique_key": "고객ID",
            "eligibility": [],
            "weights": {},
            "defaults": {"categorical": 1.0, "bucket": 1.0}
        }
        reply = "규칙을 초기화했어요."
    elif text in ("추첨", "draw", "run"):
        try:
            res = run_raffle(
                df=df,
                config=st.session_state.config,
                n_winners=st.session_state.n_winners,
                seed=st.session_state.seed
            )
            winners = res["winners"]
            st.session_state.last_winners = winners
            reply = f"추첨 완료! 상위 10명 미리보기입니다. 총 {len(winners)}명."
        except Exception as e:
            reply = f"추첨 중 오류: {e}"
    else:
        parsed = parse_rule_line(text)
        if parsed:
            col, rule = parsed
            st.session_state.config.setdefault("weights", {})
            st.session_state.config["weights"][col] = rule
            rtype = rule.get("type")
            reply = f"`{col}` 컬럼에 {rtype} 규칙을 반영했어요."
        else:
            reply = "알겠어요. 규칙 또는 명령을 이해하지 못했어요. 도움말을 참고해주세요."

    st.session_state.messages.append({"role": "assistant", "content": reply})

    if text in ("추첨", "draw", "run") and "last_winners" in st.session_state:
        with st.chat_message("assistant"):
            st.dataframe(st.session_state.last_winners.head(10))
            csv = st.session_state.last_winners.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "당첨자 CSV 다운로드",
                data=csv,
                file_name=f"winners_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
