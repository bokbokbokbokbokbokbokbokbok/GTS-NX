import streamlit as st
import pandas as pd
import pydeck as pdk

# 페이지 설정
st.set_page_config(page_title="연도변조사 지도 연동", layout="wide")

st.header("📍 연도변조사 대시보드")
st.markdown("표에서 **연번 행을 클릭**하면 해당 위치로 지도가 즉시 줌인됩니다.")

# 1. session_state 초기화 (초기 중심 좌표: 서울 시청 기준)
if "lat" not in st.session_state:
    st.session_state.lat = 37.5665
if "lon" not in st.session_state:
    st.session_state.lon = 126.9780
if "zoom" not in st.session_state:
    st.session_state.zoom = 11

# 2. 샘플 데이터 (실제 사용하시는 데이터프레임으로 대체하시면 됩니다)
# 예: df = pd.read_csv("your_data.csv") 형태
@st.cache_data
def load_data():
    return pd.DataFrame({
        "연번": [1, 2, 3, 4],
        "지점명": ["서울시청", "강남역", "여의도공원", "동대문디자인플라자"],
        "lat": [37.5665, 37.4979, 37.5219, 37.5662],
        "lon": [126.9780, 127.0276, 126.9243, 127.0092]
    })

df = load_data()

# 레이아웃을 2분할 (왼쪽: 표, 오른쪽: 지도)
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📋 연도변조사 목록")
    
    # 3. Streamlit 최신 행 선택 기능 적용
    event = st.dataframe(
        df,
        on_select="rerun",
        selection_mode="single-row",
        key="yeonbun_table",
        use_container_width=True,
        hide_index=True
    )

    # 4. 사용자가 행을 클릭했을 때 좌표값 업데이트 및 화면 새로고침
    selected_rows = event.selection.get("rows", [])
    if selected_rows:
        selected_idx = selected_rows[0]
        selected_row = df.iloc[selected_idx]
        
        # 세션 스테이트에 선택된 위치 저장
        st.session_state.lat = float(selected_row["lat"])
        st.session_state.lon = float(selected_row["lon"])
        st.session_state.zoom = 15  # 클릭 시 확대될 줌 레벨
        
        st.success(과정: f"선택됨 -> {selected_row['지점명']} (위도: {st.session_state.lat}, 경도: {st.session_state.lon})")
        st.rerun()

with col2:
    st.subheader("🗺️ 위치 지도")
    
    # 5. session_state에 저장된 좌표를 기반으로 지도 뷰 설정
    view_state = pdk.ViewState(
        latitude=st.session_state.lat,
        longitude=st.session_state.lon,
        zoom=st.session_state.zoom,
        pitch=0,
    )

    # Pydeck 레이어 설정
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[lon, lat]",
        get_color="[255, 75, 75, 200]",
        get_radius=120,
        pickable=True,
    )

    # 지도 렌더링
    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "지점명: {지점명}\n연번: {연번}\n위도: {lat}\n경도: {lon}"}
    )

    st.pydeck_chart(r, use_container_width=True)
