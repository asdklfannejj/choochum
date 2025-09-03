\
import os
import re
import io
import yaml
import pandas as pd
import streamlit as st
from datetime import datetime
from src.weighted_draw import run_raffle

st.set_page_config(page_title="가중치 추첨 챗봇", page_icon="🎯")

DEFAULT_PATH = "/mnt/data/hana_dummy_30000_20250901_084807.xlsx"

SYSTEM_TIPS = (
    "자연어로도 됩니다. 예)\\n"
    "• '20대 10명 추첨해줘' (나이 20~29세 중 10명)\\n"
    "• '서울 여성 30명' (서울 & 여성 필터 후 30명)\\n"
    "• '남성 위주로 100명' (가중치: 남성 1.1) → 가중치는 '... 위주로' 표현 지원\\n"
    "• 'seed=42', '규칙보기', '규칙초기화', '추첨'\\n"
    "규칙 입력 예시:\\n"
    "• 성별: 남성=1.0, 여성=1.1\\n"
    "• 거주지역: 서울=1.2, 경기=1.1, 기타=1.0\\n"
    "• 나이: [19-29]=1.05, [30-39]=1.10, [40-49]=1.00, [50-120]=0.95\\n"
    "자격조건 추가: 'eligibility: 나이 >= 19'"
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

uploaded = st.file_uploader("엑셀/CSV 업로드(.xlsx, .csv). 미업로드 시 기본 파일을 사용합니다.", type=["xlsx", "csv"])
if uploaded:
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded, engine="openpyxl")
else:
    if os.path.exists(DEFAULT_PATH):
        if DEFAULT_PATH.lower().endswith(".csv"):
            df = pd.read_csv(DEFAULT_PATH)
        else:
            df = pd.read_excel(DEFAULT_PATH, engine="openpyxl")
        st.caption("기본 데이터 파일을 사용 중입니다.")
    else:
        st.error("데이터 파일이 없습니다. 엑셀/CSV를 업로드해주세요.")
        st.stop()

# Cache distinct values for simple NL parsing
distinct = {col: set(map(str, df[col].dropna().unique())) for col in df.columns}

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

def add_weight(col: str, mapping: dict = None, buckets=None):
    st.session_state.config.setdefault("weights", {})
    if buckets is not None:
        st.session_state.config["weights"][col] = {"type": "bucket", "buckets": buckets}
    else:
        rule = st.session_state.config["weights"].get(col, {"type": "categorical", "mapping": {}})
        rule["type"] = "categorical"
        rule.setdefault("mapping", {})
        rule["mapping"].update(mapping or {})
        st.session_state.config["weights"][col] = rule

# VERY LIGHTWEIGHT NL PARSER FOR KOREAN COMMANDS
def parse_nl_command(text: str):
    actions = {"run": False, "messages": []}

    # seed 설정
    m = re.search(r"seed\s*=\s*(\d+)", text, re.I)
    if m:
        st.session_state.seed = int(m.group(1))
        actions["messages"].append(f"seed를 {st.session_state.seed}로 설정했어요.")

    # 인원 추출: "10명", "30명만", "20명으로"
    m = re.search(r"(\d+)\s*명", text)
    if m:
        st.session_state.n_winners = int(m.group(1))
        actions["messages"].append(f"당첨자 수를 {st.session_state.n_winners}명으로 설정했어요.")
        actions["run"] = True

    # 나이대: "20대", "30대 초반/후반" → 필터
    m = re.search(r"(\d{2})\s*대", text)
    if m and "나이" in df.columns:
        decade = int(m.group(1))
        lo, hi = decade, decade + 9
        add_eligibility(f"나이 >= {lo} and 나이 <= {hi}")
        actions["messages"].append(f"자격조건 추가: 나이 {lo}~{hi}")

    # 성별 필터
    if "성별" in df.columns:
        if "여성" in text or "여자" in text:
            add_eligibility("성별 == '여성'")
            actions["messages"].append("자격조건 추가: 성별=여성")
        elif "남성" in text or "남자" in text:
            add_eligibility("성별 == '남성'")
            actions["messages"].append("자격조건 추가: 성별=남성")

    # 지역 필터 (문자열 토큰 중 '거주지역' 값에 존재하면 적용)
    if "거주지역" in df.columns:
        tokens = re.findall(r"[가-힣A-Za-z0-9]+", text)
        region_hits = [t for t in tokens if t in distinct.get("거주지역", set())]
        if region_hits:
            # 여러 개 나오면 OR 대신 AND로 좁히지 않도록 첫 번째만 사용(간단화)
            add_eligibility(f"거주지역 == '{region_hits[0]}'")
            actions["messages"].append(f"자격조건 추가: 거주지역={region_hits[0]}")

    # "~ 위주로" 가중치 (성별/지역)
    if "위주" in text or "위주로" in text:
        # 성별 위주
        if "여성" in text or "여자" in text:
            add_weight("성별", {"여성": 1.1})
            actions["messages"].append("가중치: 여성 1.1 적용")
        if "남성" in text or "남자" in text:
            add_weight("성별", {"남성": 1.1})
            actions["messages"].append("가중치: 남성 1.1 적용")
        # 지역 위주 (등장하는 지역 토큰에 1.1 부여)
        if "거주지역" in df.columns:
            tokens = re.findall(r"[가-힣A-Za-z0-9]+", text)
            region_hits = [t for t in tokens if t in distinct.get("거주지역", set())]
            for r in region_hits:
                add_weight("거주지역", {r: 1.1})
                actions["messages"].append(f"가중치: 거주지역 {r} 1.1 적용")

    # "추첨" 명시
    if "추첨" in text or "뽑" in text:
        actions["run"] = True

    return actions

with st.sidebar:
    st.header("설정")
    st.session_state.n_winners = st.number_input("당첨자 수", 1, 100000, st.session_state.n_winners)
    st.session_state.seed = st.number_input("seed (재현성)", 0, 10**9, st.session_state.seed)
    st.text_area("도움말", SYSTEM_TIPS, height=220)

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

user_input = st.chat_input("자연어로 조건을 입력하세요. 예) '20대 여성 서울 30명 추첨'")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    reply_lines = []
    text = user_input.strip()

    # 1) 고급 명령들
    if text.lower().startswith("seed="):
        try:
            st.session_state.seed = int(text.split("=",1)[1])
            reply_lines.append(f"seed를 {st.session_state.seed}로 설정했어요.")
        except:
            reply_lines.append("seed 설정에 실패했어요. 정수를 입력해주세요.")
    elif text.startswith("당첨자수=") or text.startswith("추첨인원="):
        try:
            n = int(text.split("=",1)[1])
            st.session_state.n_winners = n
            reply_lines.append(f"당첨자 수를 {n}명으로 설정했어요.")
        except:
            reply_lines.append("당첨자 수 설정에 실패했어요. 정수를 입력해주세요.")
    elif text.startswith("eligibility:"):
        expr = text.split(":",1)[1].strip()
        add_eligibility(expr)
        reply_lines.append(f"자격조건을 추가했어요: `{expr}`")
    elif text == "규칙보기":
        reply_lines.append("현재 규칙:\n```\n" + yaml.safe_dump(st.session_state.config, allow_unicode=True, sort_keys=False) + "```")
    elif text == "규칙초기화":
        st.session_state.config = {
            "unique_key": "고객ID",
            "eligibility": [],
            "weights": {},
            "defaults": {"categorical": 1.0, "bucket": 1.0}
        }
        reply_lines.append("규칙을 초기화했어요.")
    else:
        # 2) 자연어 파싱
        acts = parse_nl_command(text)
        reply_lines.extend(acts["messages"])
        if not reply_lines:
            reply_lines.append("조건을 이해했는지 확인하려면 '규칙보기'를 입력해보세요. 예) '20대 여성 서울 30명 추첨'")

        # 3) 실행 여부
        if acts["run"]:
            try:
                res = run_raffle(
                    df=df,
                    config=st.session_state.config,
                    n_winners=st.session_state.n_winners,
                    seed=st.session_state.seed
                )
                winners = res["winners"]
                st.session_state.last_winners = winners
                reply_lines.append(f"추첨 완료! 총 {len(winners)}명. 아래에서 미리보기/다운로드 할 수 있어요.")
            except Exception as e:
                reply_lines.append(f"추첨 중 오류: {e}")

    st.session_state.messages.append({"role": "assistant", "content": "\n".join(reply_lines)})

    # 추첨했으면 바로 테이블/다운로드 제공
    if "last_winners" in st.session_state:
        with st.chat_message("assistant"):
            st.dataframe(st.session_state.last_winners.head(20))
            csv = st.session_state.last_winners.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 당첨자 CSV 다운로드",
                data=csv,
                file_name=f"winners_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
