import streamlit as st
import ezdxf
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import Polygon, MultiPolygon
import io

# ==========================================
# 1. DXF 파싱 및 지오메트리 추출 함수
# ==========================================
def parse_dxf_polylines(file_input):
    """
    DXF 파일에서 POLYLINE 및 LWPOLYLINE 좌표 세트를 추출하는 함수
    """
    try:
        # Streamlit UploadedFile 읽기 (BytesIO 변환)
        bytes_data = file_input.read()
        doc = ezdxf.read(io.BytesIO(bytes_data))
    except Exception as e:
        st.error(f"DXF 파일 읽기 오류 ({file_input.name}): {e}")
        return []

    msp = doc.modelspace()
    features = []

    for entity in msp:
        dxf_type = entity.dxftype()
        pts = []

        if dxf_type == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        elif dxf_type == 'LWPOLYLINE':
            raw_pts = entity.get_points()
            pts = [(p[0], p[1]) for p in raw_pts]

        if len(pts) >= 2:
            features.append({
                "layer": entity.dxf.layer,
                "type": dxf_type,
                "pts": pts
            })

    return features

# ==========================================
# 2. 건물 연번 부여 및 씨리얼/브이월드 엑셀 생성 함수
# ==========================================
def process_buildings_and_export_excel(building_features):
    building_records = []

    for idx, bld in enumerate(building_features, start=1):
        pts = bld["pts"]
        
        # 중심점(Centroid) 계산 (Shapely Polygon 이용)
        centroid_x, centroid_y = 0.0, 0.0
        if len(pts) >= 3:
            try:
                poly = Polygon(pts)
                centroid_x = poly.centroid.x
                centroid_y = poly.centroid.y
            except Exception:
                # Polygon 생성 실패 시 산술 평균 좌표 사용
                centroid_x = sum(p[0] for p in pts) / len(pts)
                centroid_y = sum(p[1] for p in pts) / len(pts)
        else:
            centroid_x = sum(p[0] for p in pts) / len(pts)
            centroid_y = sum(p[1] for p in pts) / len(pts)

        # 씨리얼(SEE:REAL) / 브이월드 건물정보 표준 엑셀 양식에 맞춘 레코드 구성
        building_records.append({
            "연번": f"BLD-{idx:04d}",
            "건물명": f"건물_{idx}",
            "레이어명": bld["layer"],
            "X좌표(중심)": round(centroid_x, 3),
            "Y좌표(중심)": round(centroid_y, 3),
            "정점수": len(pts),
            "비고": "CAD DXF 추출"
        })

    df = pd.DataFrame(building_records)
    return df, building_records

# ==========================================
# 3. Streamlit UI 구성
# ==========================================
st.set_page_config(page_title="GTS-NX 건물/선로 DXF 분석기", layout="wide")

st.title("🏗️ GTS-NX 건물 & 선로 DXF 오버랩 분석기")
st.write("건물 DXF와 선로 DXF를 각각 업로드하여 오버랩 시각화 및 연번 부여 엑셀을 생성합니다.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ 건물 DXF 업로드")
    building_file = st.file_uploader("건물 DXF 파일을 선택하세요", type=["dxf"], key="bld_file")

with col2:
    st.subheader("2️⃣ 선로 DXF 업로드")
    rail_file = st.file_uploader("선로 DXF 파일을 선택하세요", type=["dxf"], key="rail_file")

# 분석 시작
if building_file is not None and rail_file is not None:
    if st.button("🚀 DXF 오버랩 분석 및 연번 생성"):
        with st.spinner("DXF 파일을 파싱하고 오버랩 레이어를 생성하는 중입니다..."):
            bld_features = parse_dxf_polylines(building_file)
            rail_features = parse_dxf_polylines(rail_file)

        if not bld_features:
            st.error("건물 DXF 파일에서 유효한 POLYLINE을 찾지 못했습니다.")
        elif not rail_features:
            st.error("선로 DXF 파일에서 유효한 POLYLINE을 찾지 못했습니다.")
        else:
            st.success(f"분석 완료! (건물 객체: {len(bld_features)}개, 선로 객체: {len(rail_features)}개)")

            # 데이터 처리 및 엑셀 데이터프레임 생성
            df_buildings, building_records = process_buildings_and_export_excel(bld_features)

            # --- Plotly 시각화 (오버랩 맵) ---
            fig = go.Figure()

            # 1. 선로 그리기 (빨간색 라인)
            for rail in rail_features:
                rx = [p[0] for p in rail["pts"]]
                ry = [p[1] for p in rail["pts"]]
                fig.add_trace(go.Scatter(
                    x=rx, y=ry,
                    mode='lines',
                    line=dict(color='red', width=2),
                    name='선로',
                    hoverinfo='skip'
                ))

            # 2. 건물 그리기 (파란색 외곽선 및 연번 표시)
            for idx, rec in enumerate(building_records):
                pts = bld_features[idx]["pts"]
                bx = [p[0] for p in pts] + [pts[0][0]] # 닫힌 루프
                by = [p[1] for p in pts] + [pts[0][1]]

                # 건물 외곽선
                fig.add_trace(go.Scatter(
                    x=bx, y=by,
                    mode='lines',
                    line=dict(color='blue', width=1),
                    fill="toself",
                    fillcolor="rgba(0, 0, 255, 0.1)",
                    showlegend=False,
                    hoverinfo='text',
                    text=f"연번: {rec['연번']}<br>레이어: {rec['레이어명']}"
                ))

                # 건물 중심점에 연번 텍스트 표시
                fig.add_trace(go.Scatter(
                    x=[rec["X좌표(중심)"]],
                    y=[rec["Y좌표(중심)"]],
                    mode='text',
                    text=[rec["연번"]],
                    textposition="middle center",
                    textfont=dict(size=10, color="black"),
                    showlegend=False,
                    hoverinfo='none'
                ))

            fig.update_layout(
                title="CAD 오버랩 도면 (선로: 빨간색 / 건물: 파란색 & 연번)",
                xaxis_title="X 좌표",
                yaxis_title="Y 좌표",
                yaxis=dict(scaleanchor="x", scaleratio=1), # CAD 비율 유지
                width=1000,
                height=700
            )

            st.plotly_chart(fig, use_container_width=True)

            # --- 씨리얼 양식 엑셀 데이터 표 및 다운로드 ---
            st.subheader("📋 씨리얼(SEE:REAL) 양식 건물 정보 데이터")
            st.dataframe(df_buildings, use_container_width=True)

            # Excel 다운로드 버퍼 생성
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_buildings.to_excel(writer, index=False, sheet_name='건물정보_씨리얼양식')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 씨리얼 건물정보 엑셀 파일 다운로드",
                data=excel_data,
                file_name=f"Building_Info_Overlap.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

elif building_file is None or rail_file is None:
    st.info("💡 건물 DXF 파일과 선로 DXF 파일을 모두 업로드해 주세요.")
