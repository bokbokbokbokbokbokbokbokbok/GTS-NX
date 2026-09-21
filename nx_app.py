import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# 페이지 기본 설정
st.set_page_config(page_title="자동 연도변조사 시스템", layout="wide", page_icon="🏗️")

st.title("🏗️ 철도/도로 연도변조사 자동화 시스템")
st.write("선로 도면(DXF)만 입력하고 반경을 설정하면, 국가공간정보 API(지적/건물)와 연계하여 영향권 내 건물 리스트를 자동 추출하고 건축물대장 기반 엑셀로 출력합니다.")

# 사이드바: 파일 업로드 및 설정
with st.sidebar:
    st.header("1. 도면 파일 업로드")
    route_dxf = st.file_uploader("선로 도면 업로드 (DXF)", type=['dxf'], key='route')
    
    st.markdown("---")
    st.header("2. 조사 설정")
    buffer_radius = st.number_input("조사 반경 설정 (m)", min_value=1, max_value=500, value=30, step=5)
    run_button = st.button("공간분석 및 대장 추출 실행", use_container_width=True)

# 메인 화면 영역
if run_button:
    if route_dxf is None:
        st.warning("선로 도면(DXF 파일)을 업로드해주세요.")
    else:
        with st.spinner(f"선로 반경 {buffer_radius}m 완충구역 생성 및 지도 API 연계 중... (가상 데모)"):
            import time
            time.sleep(2) # API 호출 시간 시뮬레이션
            
            st.success("지도 API 공간분석 및 건축물대장 정보 추출 완료!")
            st.subheader(f"📍 선로 반경 {buffer_radius}m 이내 추출 건물 목록 (지도 데이터 기반)")
            
            # 지도 API(브이월드/씨리얼 등)에서 추출된 건물 명칭과 주소를 반영한 가상 데이터
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
            
            # 엑셀 다운로드 파일 생성 로직
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
