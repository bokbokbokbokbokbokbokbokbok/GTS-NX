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
import requests

st.set_page_config(page_title="자동 연도변조사 시스템", layout="wide", page_icon="🏗️")

st.title("🏗️ 철도/도로 연도변조사 자동화 시스템")
st.write("도면 선형을 바탕으로 반경을 생성하고, 영역 내에 걸쳐있는 모든 실제 건물을 실시간으로 추출합니다.")

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
        ).split(" ")[0]

        with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf') as tmp_file:
            tmp_file.write(route_dxf.getvalue())
            tmp_file_path = tmp_file.name
            
        try:
            doc = ezdxf.readfile(tmp_file_path)
            layer_list = [layer.dxf.name for layer in doc.layers]
            layer_list.sort()
            selected_layer = st.selectbox("📌 분석 선로 레이어 선택", options=layer_list)
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
    with st.spinner(f"선형 추출 및 반경 {buffer_radius}m 내 실제 건물 검색 중... (약 10~30초 소요)"):
        
        msp = doc.modelspace()
        lines_in_proj = []
        
        # 1. 도면 선형 추출
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
        
        # 2. 버퍼(반경) 생성 및 좌표 변환
        multi_line = sg.MultiLineString(lines_in_proj)
        buffer_poly = multi_line.buffer(buffer_radius)
        
        transformer = Transformer.from_crs(epsg_code, "epsg:4326", always_xy=True)
        def project_to_wgs84(x, y):
            return transformer.transform(x, y)
        
        multi_line_wgs84 = so.transform(project_to_wgs84, multi_line)
        buffer_poly_wgs84 = so.transform(project_to_wgs84, buffer_poly)
        center_lon, center_lat = buffer_poly_wgs84.centroid.coords[0]
        
        # 3. OpenStreetMap API를 통한 반경 내 실제 건물 추출 (POST 방식 적용으로 406 에러 방지)
        min_lon, min_lat, max_lon, max_lat = buffer_poly_wgs84.bounds
        overpass_url = "http://overpass-api.de/api/interpreter"
        
        overpass_query = f"""
        [out:json][timeout:25];
        (
          way["building"]({min_lat},{min_lon},{max_lat},{max_lon});
          relation["building"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out geom;
        """
        
        bldg_data = []
        try:
            headers = {
                'User-Agent': 'AutoSurveySystem/1.0 (admin@local)',
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            }
            # 406 에러 방지를 위해 GET 대신 POST 전송방식 및 data 속성 사용
            response = requests.post(overpass_url, data={'data': overpass_query}, headers=headers, timeout=30)
            
            if response.status_code == 200:
                osm_data = response.json()
                bldg_id = 1
                
                for element in osm_data.get('elements', []):
                    coords = []
                    tags = element.get('tags', {})
                    
                    if element['type'] == 'way':
                        coords = [(node['lon'], node['lat']) for node in element.get('geometry', [])]
                    elif element['type'] == 'relation':
                        for member in element.get('members', []):
                            if member.get('role') == 'outer' and 'geometry' in member:
                                coords.extend([(node['lon'], node['lat']) for node in member['geometry']])
                    
                    if len(coords) >= 3:
                        try:
                            bldg_poly = sg.MultiPoint(coords).convex_hull
                            
                            if bldg_poly.intersects(buffer_poly_wgs84):
                                center = bldg_poly.centroid
                                name = tags.get('name', '명칭없음 (도면확인 필요)')
                                addr = (tags.get('addr:street', '') + " " + tags.get('addr:housenumber', '')).strip()
                                if not addr:
                                    addr = "주소정보 없음"
                                    
                                visual_coords = list(bldg_poly.exterior.coords)
                                
                                bldg_data.append({
                                    "id": bldg_id,
                                    "lat": center.y,
                                    "lon": center.x,
                                    "name": name,
                                    "addr": addr,
                                    "polygon": visual_coords
                                })
                                bldg_id += 1
                        except Exception:
                            pass
            else:
                st.error(f"지도 API 서버 응답 오류가 발생했습니다. (상태 코드: {response.status_code})")
        except Exception as e:
            st.warning(f"인터넷 연결 문제 또는 API 서버 통신 오류로 건물을 불러오지 못했습니다: {e}")

        if len(bldg_data) > 0:
            st.success(f"공간분석 완료! 반경 내 걸쳐있는 실제 건물 총 {len(bldg_data)}동을 찾았습니다.")
        else:
            st.warning("분석은 완료되었으나, 해당 영역 내 오픈스트리트맵 상에 맵핑된 건물 정보가 없습니다.")
        
        # ---------------------------------------------------------
        # 4. 지도 시각화
        # ---------------------------------------------------------
        st.subheader("🗺️ 공간 분석 결과 (실제 걸쳐있는 건물 추출)")
        m = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="OpenStreetMap")
        
        folium.GeoJson(
            buffer_poly_wgs84,
            style_function=lambda x: {'fillColor': 'blue', 'color': 'blue', 'weight': 1, 'fillOpacity': 0.2}
        ).add_to(m)
        
        folium.GeoJson(
            multi_line_wgs84,
            style_function=lambda x: {'color': 'red', 'weight': 3}
        ).add_to(m)
        
        for bldg in bldg_data:
            folium.Polygon(
                locations=[(lat, lon) for lon, lat in bldg['polygon']],
                color='black', weight=1, fillColor='yellow', fillOpacity=0.6
            ).add_to(m)
            
            popup_html = f"<b>연번: {bldg['id']}</b><br>명칭: {bldg['name']}<br>주소: {bldg['addr']}"
            number_icon = folium.DivIcon(html=f"""
                <div style="
                    background-color: white; border: 2px solid #e74c3c; border-radius: 50%;
                    width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;
                    font-weight: bold; color: #e74c3c; box-shadow: 1px 1px 3px rgba(0,0,0,0.5);
                    font-size: 12px; margin-left: -12px; margin-top: -12px;
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
        # 5. 추출 데이터 표 영역 및 다운로드
        # ---------------------------------------------------------
        st.subheader(f"📍 추출된 건축물대장 목록 (총 {len(bldg_data)}건)")
        
        if len(bldg_data) > 0:
            output_data = {
                "연번": [b["id"] for b in bldg_data],
                "명칭": [b["name"] for b in bldg_data],
                "주소": [b["addr"] for b in bldg_data],
                "구조형식": ["조사필요"] * len(bldg_data),
                "높이/면적": ["조사필요"] * len(bldg_data),
                "층수": ["조사필요"] * len(bldg_data),
                "용도": ["조사필요"] * len(bldg_data),
            }
            df_result = pd.DataFrame(output_data)
            st.dataframe(df_result, use_container_width=True)
            
            def convert_df_to_excel(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='연도변조사 현황')
                return output.getvalue()

            st.download_button(
                label="📥 엑셀 파일로 다운로드",
                data=convert_df_to_excel(df_result),
                file_name=f"연도변조사결과_실제건물_{buffer_radius}m.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.info("해당 반경 내에 검색된 건물이 없습니다.")
