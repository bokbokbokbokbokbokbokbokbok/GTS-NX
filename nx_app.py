import streamlit as st
import ezdxf

# ==========================================
# 1. DXF 데이터 처리 함수
# ==========================================
def process_building_dxf(file_input):
    """
    Streamlit DXF 업로드 파일에서 건물/구조물 레이어의 POLYLINE 데이터를 추출하는 함수
    """
    try:
        # Streamlit UploadedFile 객체 또는 파일 경로 처리
        doc = ezdxf.read(file_input)
    except Exception as e:
        st.error(f"DXF 파일 읽기 오류: {e}")
        return []

    msp = doc.modelspace()
    buildings = []

    for entity in msp:
        dxf_type = entity.dxftype()
        pts = []

        # 1. 2D/3D POLYLINE 처리
        if dxf_type == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y) for v.dxf.vertices]

        # 2. LWPOLYLINE (경량 폴리라인) 처리
        elif dxf_type == 'LWPOLYLINE':
            raw_pts = entity.get_points()
            pts = [(p[0], p[1]) for p in raw_pts]

        if pts:
            layer_name = entity.dxf.layer
            buildings.append({
                "layer": layer_name,
                "type": dxf_type,
                "coordinates": pts
            })

    return buildings


# ==========================================
# 2. Streamlit UI 화면 구성
# ==========================================
st.set_page_config(page_title="GTS-NX DXF 분석기", layout="wide")

st.title("🏗️ GTS-NX DXF 데이터 분석기")
st.write("DXF 파일을 업로드하여 건물 및 구조물 폴리라인 데이터를 추출합니다.")

# 파일 업로드 컴포넌트
uploaded_file = st.file_uploader("DXF 파일을 선택하세요", type=["dxf"])

if uploaded_file is not None:
    st.info(f"선택된 파일: **{uploaded_file.name}**")
    
    # 처리 버튼
    if st.button("DXF 데이터 파싱 시작"):
        with st.spinner("DXF 파일을 분석하는 중입니다..."):
            extracted_data = process_building_dxf(uploaded_file)
            
        if extracted_data:
            st.success(f"성공적으로 총 {len(extracted_data)}개의 객체를 추출했습니다!")
            
            # 결과 표로 출력
            st.subheader("추출된 데이터 요약")
            st.dataframe(extracted_data)
        else:
            st.warning("파일에서 추출할 수 있는 POLYLINE 객체를 찾지 못했습니다.")
else:
    st.write("👈 좌측 상단에서 DXF 파일을 업로드해 주세요.")
