import streamlit as st
import pandas as pd
from io import BytesIO
import tempfile
import os
import ezdxf
from pyproj import Transformer
import shapely.geometry as sg
import shapely.ops as so
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
    with st.spinner(f"DXF 선형 추출 및 반경 {buffer_radius}m 폴리곤 생성 중..."):
        
        msp = doc.modelspace()
        lines_in_proj = []
        
        # 1. 도면에서 선택한 레이어의 실제 선형 데이터 추출 (미터 단위 좌표계)
        for entity in msp.query(f'*[layer=="{selected_layer}"]'):
            if entity.dxftype() == 'LINE':
                start, end = entity.dxf.start, entity.dxf.end
                lines_in_proj.append(sg.LineString([(start.x, start.y), (end.x, end.y)]))
            elif entity.dxftype() == 'LWPOLYLINE':
                pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                if len(pts) > 1:
                    lines_in_proj.append(sg.LineString(pts))

        if not lines_in_proj:
            st.error("⚠️ 선택한 레이어에 선형 데이터가 없습니다.")
            os.remove(tmp_file_path)
            st.stop()
            
        os.remove(tmp_file_path)
        
        # 2. 공간 연산: 선형 병합 및 지정된 반경(m)만큼 진짜 다각형(Buffer) 생성
        multi_line = sg.MultiLineString(lines_in_proj)
        buffer_poly = multi_line.buffer(buffer_radius) # 픽셀이 아닌 실제 미터 단위 버퍼
        
        # 3. 좌표계 변환 (캐드 좌표 -> 지도 위경도 WGS84)
        transformer = Transformer.from_crs(epsg_code, "epsg:4326", always_xy=True)
        def project_to_wgs84(x, y):
            return transformer.transform(x, y)
        
        multi_line_wgs84 = so.transform(project_to_wgs84, multi_line)
        buffer_poly_wgs84 = so.transform(project_to_wgs84, buffer_poly)
        
        # 지도 중심점 찾기
        center_lon, center_lat = buffer_poly_wgs84.centroid.coords[0]
        
        st.success("실제 반경 기반 공간분석 완료!")
        
        # ---------------------------------------------------------
        # 지도 시각화
        # ---------------------------------------------------------
        st.subheader("🗺️ 공간 분석 결과 (연번 마커 적용)")
        m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles="OpenStreetMap")
        
        # 고정된 반경 다각형 (지도를 확대/축소해도 실제 반경 영역 유지)
        folium.GeoJson(
            buffer_poly_wgs84,
            style_function=lambda x: {'fillColor': 'blue', 'color': 'blue', 'weight': 1, 'fillOpacity': 0.3},
            tooltip=f"영향권 반경 {buffer_radius}m"
        ).add_to(m)
        
        # 캐드 선형
        folium.GeoJson(
            multi_line_wgs84,
            style_function=lambda x: {'color': 'red', 'weight': 3}
        ).add_to(m)
        
        # 가상 건물 마커 생성 (선형을 따라 고르게 배치)
        bldg_data = []
        for i in range(1, 6):
            # 선형의 10%, 30%, 50%, 70%, 90% 위치에 가상 건물 배치
            pt = multi_line_wgs84.interpolate(i * 0.18, normalized=True)
            bldg_data.append({
                "id": i,
                "lat": pt.y + 0.0001, # 선 옆으로 살짝 이동
                "lon": pt.x + 0.0001,
                "name": ["상가", "단독주택", "창고", "비닐하우스", "주민센터"][i-1],
                "addr": f"인근 지번 10-{i}"
            })
            
        # 지도에 번호가 적힌 깔끔한 원형 마커 추가
        for bldg in bldg_data:
            popup_html = f"<b>연번: {bldg['id']}</b><br>명칭: {bldg['name']}<br>주소: {bldg['addr']}"
            
            # CSS를 활용한 숫자 마커 (글자 겹침 해결)
            number_icon = folium.DivIcon(html=f"""
                <div style="
                    background-color: white; border: 2.5px solid #28a745; border-radius: 50%;
                    width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
                    font-weight: 900; color: #28a745; box-shadow: 2px 2px 4px rgba(0,0,0,0.4);
                    font-size: 14px; margin-left: -16px; margin-top: -16px;
                ">{bldg['id']}</div>
            """)
            
            folium.Marker(
                location=[bldg['lat'], bldg['lon']],
                icon=number_icon,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=f"연번 {bldg['id']} ({bldg['name']})"
            ).add_to(m)
            
        st_folium(m, width="100%", height=600, returned_objects=[])

        st.markdown("---")
        
        # ---------------------------------------------------------
        # 추출 데이터 표 영역 및 다운로드
        # ---------------------------------------------------------
        st.subheader(f"📍 추출된 건축물대장 목록 (총 {len(bldg_data)}건)")
        
        output_data = {
            "연번": [b["id"] for b in bldg_data],
            "명칭": [b["name"] for b in bldg_data],
            "도로명": ["-"] * len(bldg_data),
            "지번": [b["addr"] for b in bldg_data],
            "구조형식": ["철근콘크리트구조", "일반철골구조", "경량철골구조", "", "철근콘크리트구조"],
            "높이(m)\n(건축면적, m2)": ["12.5 (135)", "15.0 (300)", "5.5 (250)", "", "20.1 (500)"],
            "층수\n(지하/지상)": ["1/3", "1/4", "0/1", "", "2/5"],
            "용도": ["제1종근린생활시설", "단독주택", "창고시설", "동식물관련시설", "공공업무시설"],
            "준공년도": ["20150512", "20200115", "20081020", "", "20180911"],
            "기한": ["10~20년", "10년 미만", "20~30년", "", "10년 미만"],
            "등급": ["B", "A", "C", "", "A"],
            "기초형식\n(내진설계)": ["지내력기초(내진적용)", "내진적용", "내진 비적용", "", "말뚝기초(내진적용)"],
            "건축물대장\n유무": ["O", "O", "O", "X", "O"],
            "도면\n보유현황": ["X", "O", "X", "", "O"],
            "비고(지역 및 구역 등)": ["상업지역", "제1종일반주거지역", "자연녹지", "개발제한구역", "제2종일반주거지역"]
        }
        
        df_result = pd.DataFrame(output_data)
        
        # Streamlit 표 시각화
        st.dataframe(df_result, use_container_width=True)
        
        # 엑셀 다운로드
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
