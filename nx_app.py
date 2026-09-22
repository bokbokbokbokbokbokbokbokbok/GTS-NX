import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# 페이지 설정
st.set_page_config(page_title="위치 연동 지도 앱", layout="wide")

st.title("📍 연번 선택 지도 줌인 시스템")

# 1. 샘플 데이터프레임 생성 (실제 데이터로 교체하여 사용하세요)
@st.cache_data
def load_data():
    return pd.DataFrame({
        '연번': [1, 2, 3],
        '장소명': ['서울시청', 'N서울타워', '경복궁'],
        'lat': [37.5665, 37.5519, 37.5796],
        'lon': [126.9780, 126.9918, 126.9770]
    })

df = load_data()

st.subheader("📋 장소 목록 (행을 클릭하면 지도가 이동합니다)")

# 2. 표 출력 및 단일 행 선택 이벤트 활성화
# 경고 방지를 위해 컨테이너 활용 또는 표준 파라미터 사용
event = st.dataframe(
    df,
    on_select="rerun",
    selection_mode="single-row",
    hide_index=True
)

# 3. 기본 지도 중심 설정 (선택된 값이 없으면 서울 시청 기준)
map_lat, map_lon = 37.5665, 126.9780
map_zoom = 12

# 4. 사용자가 행을 선택했을 경우 좌표 업데이트
selected_rows = event.selection.rows

if selected_rows:
    selected_idx = selected_rows[0]
    map_lat = df.loc[selected_idx, 'lat']
    map_lon = df.loc[selected_idx, 'lon']
    map_zoom = 16  # 선택 시 줌인 레벨 확대
    
    st.info(f"선택된 장소: **{df.loc[selected_idx, '장소명']}** (위도: {map_lat}, 경도: {map_lon})")

# 5. Folium 지도 객체 생성
m = folium.Map(location=[map_lat, map_lon], zoom_start=map_zoom)

# 6. 모든 마커 지도에 표시
for idx, row in df.iterrows():
    # 선택된 마커는 색상을 다르게 하거나 팝업을 다르게 줄 수도 있습니다.
    is_selected = selected_rows and (selected_rows[0] == idx)
    icon_color = "red" if is_selected else "blue"
    
    folium.Marker(
        location=[row['lat'], row['lon']], 
        popup=f"[{row['연번']}] {row['장소명']}",
        tooltip=row['장소명'],
        icon=folium.Icon(color=icon_color, icon="info-sign")
    ).add_to(m)

# 7. Streamlit에 지도 렌더링
st_folium(m, width="100%", height=500)
