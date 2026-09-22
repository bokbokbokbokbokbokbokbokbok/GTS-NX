import pandas as pd
import pydeck as pdk
import streamlit as st

# 페이지 레이아웃 설정 (넓게 보기)
st.set_page_config(
    page_title="연도변 조사 맵 뷰어", page_icon="🗺️", layout="wide"
)

st.title("🗺️ 연도변 조사 위치 뷰어 및 줌인/초기화 기능")

# 1. 샘플 데이터 생성 (실제 사용 중이신 데이터프레임으로 대체 가능합니다)
if "df_data" not in st.session_state:
  st.session_state["df_data"] = pd.DataFrame({
      "연번": [1, 2, 3, 4],
      "조사명": [
          "서울 지역 조사 A",
          "강남 지역 조사 B",
          "홍대 지역 조사 C",
          "여의도 지역 조사 D",
      ],
      "위도": [37.5665, 37.4979, 37.5563, 37.5219],
      "경도": [126.9780, 127.0276, 126.9236, 126.9242],
  })

df = st.session_state["df_data"]

# 2. 기본 중심 좌표 및 줌 레벨 정의 (초기 상태용)
DEFAULT_LAT = 37.5665
DEFAULT_LON = 126.9780
DEFAULT_ZOOM = 11

# 세션 상태 초기화 (좌표 값이 없으면 기본값으로 설정)
if "zoom_lat" not in st.session_state:
  st.session_state["zoom_lat"] = DEFAULT_LAT
if "zoom_lon" not in st.session_state:
  st.session_state["zoom_lon"] = DEFAULT_LON
if "zoom_zoom" not in st.session_state:
  st.session_state["zoom_zoom"] = DEFAULT_ZOOM

# 3. 화면 레이아웃 구성 (2단 컬럼: 좌측 테이블 / 우측 지도)
col1, col2 = st.columns([1, 1])

with col1:
  st.subheader("📋 연도변 조사 테이블")
  st.info(
      "💡 테이블에서 원하는 행을 클릭하시면 지도가 해당 위치로 줌인됩니다."
  )

  # 데이터프레임 선택 기능 활성화
  event = st.dataframe(
      df,
      on_select="rerun",
      selection_mode="single-row",
      key="investigation_table",
      use_container_width=True,
  )

  # 행이 선택되었을 때의 처리 로직
  selected_rows = event.selection.rows
  if selected_rows:
    selected_idx = selected_rows[0]
    selected_row_data = df.iloc[selected_idx]

    # 세션 상태에 선택된 행의 좌표와 확대된 줌 레벨 저장
    st.session_state["zoom_lat"] = selected_row_data["위도"]
    st.session_state["zoom_lon"] = selected_row_data["경도"]
    st.session_state["zoom_zoom"] = 15  # 줌인 레벨 (숫자가 클수록 확대)

with col2:
  st.subheader("📍 위치 지도")

  # 원래 상태로 되돌리기(초기화) 버튼
  if st.button("🔄 원래 상태로 되돌리기 (초기화)", use_container_width=True):
    st.session_state["zoom_lat"] = DEFAULT_LAT
    st.session_state["zoom_lon"] = DEFAULT_LON
    st.session_state["zoom_zoom"] = DEFAULT_ZOOM
    st.rerun()  # 화면을 새로고침하여 초기 상태 적용

  # PyDeck을 활용한 지도 뷰어 설정 (세션 상태의 좌표를 반영)
  view_state = pdk.ViewState(
      latitude=st.session_state["zoom_lat"],
      longitude=st.session_state["zoom_lon"],
      zoom=st.session_state["zoom_zoom"],
      pitch=0,
  )

  # 지도 마커 레이어 설정
  layer = pdk.Layer(
      "ScatterplotLayer",
      data=df,
      get_position="[경도, 위도]",
      get_color="[255, 75, 75, 200]",
      get_radius=250,
      pickable=True,
  )

  # 맵 객체 생성
  r = pdk.Deck(
      layers=[layer],
      initial_view_state=view_state,
      tooltip={"text": "조사명: {조사명}\n연번: {연번}"},
  )

  # Streamlit에 지도 렌더링
  st.pydeck_chart(r, use_container_width=True)
