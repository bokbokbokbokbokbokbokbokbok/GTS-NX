import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🏛️ 건물대장 연번 표 & CAD 수치지도 오버랩")

# 1. 건물대장 및 CAD 구역 연치 데이터 (가상 데이터 예시)
# 실제 환경에서는 ezdxf / geopandas를 통해 DXF 파일을 읽어 좌표(EPSG:5186 등)를 WGS84(EPSG:4326)로 변환하여 사용합니다.
building_data = [
    {
        "연번": 1, "건물명": "1호관 (본관)", "주용도": "업무시설", "층수": "지상 5층",
        "lat": 37.5665, "lng": 126.9780,
        "polygon": [[37.5663, 126.9777], [37.5667, 126.9777], [37.5667, 126.9783], [37.5663, 126.9783]]
    },
    {
        "연번": 2, "건물명": "2호관 (연구동)", "주용도": "교육연구시설", "층수": "지상 3층",
        "lat": 37.5672, "lng": 126.9791,
        "polygon": [[37.5670, 126.9788], [37.5674, 126.9788], [37.5674, 126.9794], [37.5670, 126.9794]]
    },
    {
        "연번": 3, "건물명": "3호관 (복지관)", "주용도": "근린생활시설", "층수": "지상 2층",
        "lat": 37.5658, "lng": 126.9772,
        "polygon": [[37.5656, 126.9769], [37.5660, 126.9769], [37.5660, 126.9775], [37.5656, 126.9775]]
    }
]

df = pd.DataFrame(building_data)

# 레이아웃 구성 (좌측: 표, 우측: 수치지도 오버랩)
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📋 건물대장 연번목록")
    
    # 세션 상태를 이용해 표에서 선택한 연번 강조
    selected_no = st.selectbox("🎯 지도에서 강조할 연번 선택", df["연번"].tolist())
    
    # 데이터프레임 출력
    st.dataframe(
        df[["연번", "건물명", "주용도", "층수"]],
        use_container_width=True,
        hide_index=True
    )

with col2:
    st.subheader("🗺️ CAD 수치지도 & 연번 위치 오버랩")
    
    # 지도 중심 설정
    center_lat = df["lat"].mean()
    center_lng = df["lng"].mean()
    
    # 기본 지도 생성 (VWorld/위성지도 타일 스타일 적용 가능)
    m = folium.Map(location=[center_lat, center_lng], zoom_start=17)
    
    # CAD 수치지도 선형 데이터(Polygon) 및 연번 오버랩 출력
    for _, row in df.iterrows():
        is_selected = (row["연번"] == selected_no)
        
        # 1) CAD 수치지도 폴리곤 레이어 (경계선)
        folium.Polygon(
            locations=row["polygon"],
            color="#FF3333" if is_selected else "#2B579A",  # 선택된 건물은 빨간색 강조
            weight=3 if is_selected else 2,
            fill=True,
            fill_color="#FF8888" if is_selected else "#3388ff",
            fill_opacity=0.4 if is_selected else 0.2,
            tooltip=f"CAD 레이어 [연번 {row['연번']}]"
        ).add_to(m)
        
        # 2) 연번 라벨 마커 (숫자 표기)
        icon_html = f"""
            <div style="
                font-size: 12px;
                font-weight: bold;
                color: white;
                background-color: {'#FF3333' if is_selected else '#1E3A8A'};
                border-radius: 4px;
                padding: 2px 6px;
                border: 1px solid white;
                box-shadow: 1px 1px 4px rgba(0,0,0,0.4);
                white-space: nowrap;
            ">
                No.{row['연번']}
            </div>
        """
        
        folium.Marker(
            location=[row["lat"], row["lng"]],
            popup=f"<b>[연번 {row['연번']}] {row['건물명']}</b><br>{row['주용도']}",
            icon=folium.DivIcon(html=icon_html, icon_size=(40, 20))
        ).add_to(m)

    # 마우스 조작 가능한 Folium 지도 출력
    st_folium(m, width="100%", height=550)
