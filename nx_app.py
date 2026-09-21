import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import tempfile
import os
import ezdxf

# 지도 시각화를 위한 라이브러리 추가
import folium
from streamlit_folium import st_folium

# 페이지 기본 설정 (와이드 모드)
st.set_page_config(page_title="자동 연도변조사 시스템", layout="wide", page_icon="🏗️")

st.title("🏗️ 철도/도로 연도변조사 자동화 시스템")
st.write("선로 도면(DXF)을 입력하고 기준 레이어와 반경을 설정하면, 국가공간정보 API와 연계하여 영향권 내 건물을 추출하고 지도 시각화 및 엑셀로 출력합니다.")

# 사이드바: 파일 업로드 및 설정
with st.sidebar:
    st.header("1. 도면 파일 업로드")
    route_dxf = st.file_uploader("선로 도면 업로드 (DXF)", type=['dxf'], key='route')
    
    selected_layer = None
    
    if route_dxf is not None:
        st.success("도면 업로드 완료! 레이어를 분석합니다.")
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
            st.error(f"도면을 분석하는 중 오류가 발생했습니다: {e}")
            selected_layer = None
        finally:
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
    
    st.markdown("---")
    st.header("2. 조사 설정")
    buffer_radius = st.number_input("조사 반경 설정 (m)", min_value=1, max_value=500, value=30, step=5)
    
    run_button_disabled = True if (route_dxf is None or selected_layer is None) else False
    run_button = st.button("공간분석 및 대장 추출 실행", use_container_width=True, disabled=run_button_disabled)

# 메인 화면 영역
if run_button:
    with st.spinner(f"'{selected_layer}' 레이어 기준 반경 {buffer_radius}m 완충구역 생성 및 지도 생성 중... (데모)"):
        import time
        time.sleep(2) 
        
        st.success("지도 공간분석 및 건축물대장 정보 추출 완료!")
        
        # ---------------------------------------------------------
        # 1. 지도 시각화 영역 (Folium 활용)
        # ---------------------------------------------------------
        st.subheader("🗺️ 공간 분석 결과 시각화 (선형 및 반경 오버랩)")
        
        # 가상의 선로 좌표 및 지도 중심점 (고양시 도내동 인근으로 설정)
        map_center = [37.631, 126.868]
        m = folium.Map(location=map_center, zoom_start=15, tiles="CartoDB positron") # 깔끔한 배경지도
        
        # (1) 선로 선형 그리기 (DXF에서 추출했다고 가정한 좌표)
        track_coords = [[37.628, 126.862], [37.631, 126.868], [37.634, 126.875]]
        folium.PolyLine(
            track_coords, 
            color="red", 
            weight=3, 
            opacity=0.8,
            tooltip=f"선로 중심선 ({selected_layer})"
        ).add_to(m)
        
        # (2) 반경(Buffer) 그리기 (입력한 buffer_radius 크기에 비례하여 굵기 임시 설정)
        # 실제 개발 시에는 geopandas의 buffer 폴리곤 객체를 geojson으로 변환하여 올립니다.
        buffer_weight = buffer_radius * 1.5 
        folium.PolyLine(
            track_coords, 
            color="blue", 
            weight=buffer_weight, 
            opacity=0.2, 
            tooltip=f"분석 반경 {buffer_radius}m"
        ).add_to(m)
        
        # (3) 추출된 건물 마커 그리기
        bldg_coords = [
            {"name": "도내1동주민센터(가칭)", "loc": [37.6315, 126.8685]},
            {"name": "새마을금고 도내지점", "loc": [37.6305, 126.8675]},
            {"name": "현대카센터", "loc": [37.6320, 126.8690]},
            {"name": "명칭없음(비닐하우스)", "loc": [37.6290, 126.8640]}
        ]
        
        for bldg in bldg_coords:
            folium.Marker(
                bldg["loc"], 
                popup=bldg["name"], 
                tooltip="건축물대장 추출 완료",
                icon=folium.Icon(color="green", icon="home")
            ).add_to(m)
            
        # 스트림릿 화면에 지도 띄우기 (화면 꽉 차게)
        st_folium(m, width=1500, height=500, returned_objects=[])

        st.markdown("---")
        
        # ---------------------------------------------------------
        # 2. 추출 데이터 표 영역 및 다운로드
        # ---------------------------------------------------------
        st.subheader(f"📍 추출된 건축물대장 목록 (총 {len(bldg_coords)}건)")
        
        output_data = {
            "연번": [1, 2, 3, 4],
            "명칭": ["도내1동주민센터(가칭)", "새마을금고 도내지점", "현대카센터", "명칭없음(비닐하우스)"],
            "도로명": ["고양대로 123", "고양대로 125", "고양대로 130", ""],
            "지번": ["도내동 11-1", "도내동 11-2", "도내동 12-5", "도내동 144-1"],
            "구조형식": ["철근콘크리트구조", "경량철골구조", "일반철골구조", ""],
            "높이(m)\n(건축면적, m2)": ["12.5 (135.2)", "5.5 (250.0)", "15.0 (300.5)", ""],
            "층수\n(지하/지상)": ["1/3", "0/1", "1/4", ""],
            "용도": ["제1종근린생활시설", "제2종근린생활시설", "자동차관련시설", ""],
            "준공년도": ["20150512", "20081020", "20200115", ""],
            "기한": ["10~20년", "20~30년", "10년 미만", ""],
            "등급": ["B", "C", "A", ""],
            "기초형식\n(내진설계)": ["지내력기초(내진적용)", "내진 비적용", "내진적용", ""],
            "건축물대장\n유무": ["O", "O", "O", "X"],
            "도면\n보유현황": ["X", "X", "O", ""],
            "비고(지역 및 구역 등)": ["제1종일반주거지역", "상업지역", "지구단위계획구역", "개발제한구역"]
        }
        
        df_result = pd.DataFrame(output_data)
        st.dataframe(df_result, use_container_width=True)
        
        def convert_df_to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='연도변조사 현황')
            processed_data = output.getvalue()
            return processed_data

        excel_data = convert_df_to_excel(df_result)
        
        st.download_button(
            label="📥 엑셀 파일로 다운로드 (연도변조사 현황 양식)",
            data=excel_data,
            file_name=f"연도변조사결과_반경{buffer_radius}m.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
