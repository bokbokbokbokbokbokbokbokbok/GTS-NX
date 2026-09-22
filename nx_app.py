import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# 1. 샘플 데이터 (연번, 이름, 위도, 경도)
df = pd.DataFrame({
    '연번': [1, 2, 3],
    '장소명': ['위치 A', '위치 B', '위치 C'],
    'lat': [37.5665, 37.5519, 37.5796],
    'lon': [126.9780, 126.9918, 126.9770]
})

st.subheader("📍 지점 목록")

# 2. 표 출력 및 행 선택 이벤트 설정
event = st.dataframe(
    df,
    on_select="rerun",
    selection_mode="single-row",
    use_container_width=True
)

# 3. 기본 지도 중심 설정 (선택된 값이 없으면 서울 중심)
map_lat, map_zoom = 37.5665, 12
selected_rows = event.selection.rows

if selected_rows:
    # 선택된 행의 데이터 가져오기
    selected_idx = selected_rows[0]
    map_lat = df.loc[selected_idx, 'lat']
    map_lon = df.loc[selected_idx, 'lon']
    map_zoom = 16  # 줌인 레벨 높이기
else:
    map_lon = 126.9780

# 4. 지도 생성 및 렌더링
m = folium.Map(location=[map_lat, map_lon], zoom_start=map_zoom)

# 마커 추가
for idx, row in df.iterrows():
    folium.Marker(
        [row['lat'], row['lon']], 
        popup=f"{row['연번']}: {row['장소명']}"
    ).add_to(m)

st_folium(m, width="100%", height=400)
