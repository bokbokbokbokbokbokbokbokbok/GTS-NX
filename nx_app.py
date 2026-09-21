import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import tempfile
import os
import ezdxf
from pyproj import Transformer
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="자동 연도변조사 시스템", layout="wide", page_icon="🏗️")

st.title("🏗️ 철도/도로 연도변조사 자동화 시스템")
st.write("실제 DXF 선형을 추출하여 지도에 투영하고, 주변 건물의 연번과 대장 정보를 시각화합니다.")

# 사이드바: 파일 업로드 및 설정
with st.sidebar:
    st.header("1. 도면 파일 업로드")
    route_dxf = st.file_uploader("선로 도면 업로드 (DXF)", type=['dxf'], key='route')
    
    selected_layer = None
    epsg_code = None
    
    if route_dxf is not None:
        # 캐드 좌표계 선택 (국내 도면은 주로 5186, 5187 사용)
        epsg_code = st.selectbox(
            "📍 도면 좌표계 선택", 
            options=["epsg:5186 (중부원점)", "epsg:5187 (동부원점)", "epsg:5179 (UTM-K)", "epsg:4326 (WGS84)"],
            index=0,
            help="도면 작성 시 사용된 좌표계를 선택하세요. (기본값: 중부원점)"
        ).split(" ")[0]

        with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf') as tmp_file:
            tmp_file.write(route_dxf.getvalue())
            tmp_file_path = tmp_file.name
            
        try:
            doc = ezdxf.readfile(tmp_file_path)
            layer_list = [layer.dxf.name for layer in doc.layers]
            layer_list.sort()
            
            selected_layer = st.selectbox(
                "📌 분석에 사용할 선로 레이어 선택", 
                options=layer_list, 
                help="도면에서 선로 선형(중심선 등)이 그려진 실제 레이어를 선택하세요."
            )
        except Exception as e:
            st.error(f"도면 분석 오류: {e}")
            selected_layer = None
    
    st.markdown("---")
    st.header("2. 조사 설정")
    buffer_radius = st.number_input("조사 반경 설정 (m)", min_value=1, max_value=500, value=30, step=5)
    
    run_button_disabled = True if (route_dxf is None or selected_layer is None) else False
    run_button = st.button("공간분석 및 대장 추출 실행", use_container_width=True, disabled=run_button_disabled)

# 메인 화면 영역
if run_button:
    with st.spinner(f"DXF 선형 추출 및 '{selected_layer}' 레이어 변환 중..."):
        
        # 1. DXF 도면에서 선택한 레이어의 실제 선형 데이터 추출
        transformer = Transformer.from_crs(epsg_code, "epsg:4326", always_xy=True)
        msp = doc.modelspace()
        
        extracted_lines = []
        all_lats, all_lons = [], []
        
        # 선택한 레이어의 LINE 및 LWPOLYLINE 객체 좌표 추출
        for entity in msp.query(f'*[layer=="{selected_layer}"]'):
            if entity.dxftype() == 'LINE':
                start, end = entity.dxf.start, entity.dxf.end
                lon1, lat1 = transformer.transform(start.x, start.y)
                lon2, lat2 = transformer.transform(end.x, end.y)
                extracted_lines.append([(lat1, lon1), (lat2, lon2)])
                all_lats.extend([lat1, lat2])
                all_lons.extend([lon1, lon2])
                
            elif entity.dxftype() == 'LWPOLYLINE':
                pts = []
                for point in entity.get_points(format='xy'):
                    lon, lat = transformer.transform(point[0], point[1])
                    pts.append((lat, lon))
                    all_lats.append(lat)
                    all_lons.append(lon)
                if pts:
                    extracted_lines.append(pts)

        if not extracted_lines:
            st.error("⚠️ 선택한 레이어에 선형(LINE 또는 LWPOLYLINE) 데이터가 없습니다. 다른 레이어를 선택해주세요.")
            os.remove(tmp_file_path)
            st.stop()
            
        os.remove(tmp_file_path) # 임시파일 삭제
        
        # 지도 중심점 계산 (추출된 선형들의 정중앙)
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        
        st.success("도면 선형 추출 및 지도 매핑 완료!")
        
        # 2. 지도 시각화 (OpenStreetMap 적용)
        st.subheader("🗺️ 공간 분석 결과 (실제 선형 적용)")
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="OpenStreetMap")
        
        # 추출한 실제 DXF 선형 그리기
        for line_coords in extracted_lines:
            # 선형 자체
            folium.PolyLine(line_coords, color="red", weight=4, opacity=1.0).add_to(m)
            # 버퍼(반경) 시각화 - weight를 반경에 비례하여 굵게 설정
            folium.PolyLine(line_coords, color="blue", weight=buffer_radius*2, opacity=0.3).add_to(m)
        
        # 3. 추출 건물 동적 마커 생성 (선형 주변으로 배치)
        # ※ 실제 구축 시에는 이 위치에 Vworld WFS API를 호출하여 반경 내 실제 건물을 가져오는 코드가 들어갑니다.
        bldg_data = [
            {"id": 1, "name": "주택", "lat": center_lat + 0.0001, "lon": center_lon + 0.0002, "addr": "인근 지번 11-1"},
            {"id": 2, "name": "상가", "lat": center_lat - 0.0002, "lon": center_lon - 0.0001, "addr": "인근 지번 11-2"},
            {"id": 3, "name": "창고", "lat": center_lat + 0.0003, "lon": center_lon - 0.0002, "addr": "인근 지번 12-5"},
            {"id": 4, "name": "비닐하우스", "lat": center_lat - 0.0001, "lon": center_lon + 0.0003, "addr": "인근 지번 144-1"}
        ]
        
        for bldg in bldg_data:
            # 연번을 마커에 표시하기 위해 DivIcon과 기본 마커 조합 사용
            popup_html = f"<b>연번: {bldg['id']}</b><br>명칭: {bldg['name']}<br>주소: {bldg['addr']}"
            
            # 마커 추가
            folium.Marker(
                location=[bldg['lat'], bldg['lon']],
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=f"[연번 {bldg['id']}] {bldg['name']}",
                icon=folium.Icon(color="green", icon="info-sign")
            ).add_to(m)
            
            # 지도 위에 텍스트로 연번 직접 표시
            folium.map.Marker(
                [bldg['lat'], bldg['lon']],
                icon=folium.DivIcon(
                    icon_size=(150,36),
                    icon_anchor=(-10, -10),
                    html=f'<div style="font-size: 14pt; color: black; font-weight: 900; text-shadow: 1px 1px 2px white;">No.{bldg["id"]}</div>'
                )
            ).add_to(m)
            
        st_folium(m, width="100%", height=600, returned_objects=[])

        st.markdown("---")
        
        # 4. 추출 데이터 표 영역 및 다운로드
        st.subheader(f"📍 추출된 건축물대장 목록 (총 {len(bldg_data)}건)")
        
        output_data = {
            "연번": [b["id"] for b in bldg_data],
            "명칭": [b["name"] for b in bldg_data],
            "도로명": ["-", "-", "-", "-"],
            "지번": [b["addr"] for b in bldg_data],
            "구조형식": ["철근콘크리트구조", "일반철골구조", "경량철골구조", ""],
            "높이(m)\n(건축면적, m2)": ["12.5 (135.2)", "15.0 (300.5)", "5.5 (250.0)", ""],
            "층수\n(지하/지상)": ["1/3", "1/4", "0/1", ""],
            "용도": ["단독주택", "제1종근린생활시설", "창고시설", "동식물관련시설"],
            "준공년도": ["20150512", "20200115", "20081020", ""],
            "기한": ["10~20년", "10년 미만", "20~30년", ""],
            "등급": ["B", "A", "C", ""],
            "기초형식\n(내진설계)": ["지내력기초(내진적용)", "내진적용", "내진 비적용", ""],
            "건축물대장\n유무": ["O", "O", "O", "X"],
            "도면\n보유현황": ["X", "O", "X", ""],
            "비고(지역 및 구역 등)": ["제1종일반주거지역", "상업지역", "지구단위계획구역", "개발제한구역"]
        }
        
        df_result = pd.DataFrame(output_data)
        st.dataframe(df_result, use_container_width=True)
        
        def convert_df_to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='연도변조사 현황')
            return output.getvalue()

        st.download_button(
            label="📥 엑셀 파일로 다운로드 (연도변조사 현황 양식)",
            data=convert_df_to_excel(df_result),
            file_name=f"연도변조사결과_반경{buffer_radius}m.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
