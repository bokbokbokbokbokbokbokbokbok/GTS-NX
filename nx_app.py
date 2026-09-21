import streamlit as st
import ezdxf
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import Polygon, LineString, MultiLineString
import io

# ==========================================
# 1. DXF 파일에서 전체 레이어 목록 추출
# ==========================================
def get_dxf_layers(file_input):
    """
    DXF 파일 내 존재하는 모든 레이어 이름 목록 반환
    """
    try:
        file_input.seek(0)
        bytes_data = file_input.read()
        # ezdxf.read()를 위한 StringIO 텍스트 스트림 변환
        text_data = bytes_data.decode('utf-8', errors='ignore')
        doc = ezdxf.read(io.StringIO(text_data))
        
        layers = [layer.dxf.name for layer in doc.layers]
        return sorted(layers)
    except Exception as e:
        st.error(f"DXF 레이어 읽기 오류 ({file_input.name}): {e}")
        return []

# ==========================================
# 2. DXF 레이어별 파싱 함수
# ==========================================
def parse_dxf_by_layer(file_input, target_layer_name):
    """
    DXF 파일에서 지정한 레이어(target_layer_name)에 속한 POLYLINE/LWPOLYLINE 좌표 추출
    """
    try:
        file_input.seek(0)
        bytes_data = file_input.read()
        text_data = bytes_data.decode('utf-8', errors='ignore')
        doc = ezdxf.read(io.StringIO(text_data))
    except Exception as e:
        st.error(f"DXF 파일 읽기 오류 ({file_input.name}): {e}")
        return []

    msp = doc.modelspace()
    features = []

    for entity in msp:
        layer_name = entity.dxf.layer if hasattr(entity.dxf, 'layer') else ""
        
        # 선택한 레이어와 일치하는 객체만 추출 (대소문자 구분 없음)
        if target_layer_name.strip().lower() != layer_name.strip().lower():
            continue

        dxf_type = entity.dxftype()
        pts = []

        if dxf_type == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        elif dxf_type == 'LWPOLYLINE':
            raw_pts = entity.get_points()
            pts = [(p[0], p[1]) for p in raw_pts]

        if len(pts) >= 2:
            features.append({
                "layer": layer_name,
                "type": dxf_type,
                "pts": pts
            })

    return features

# ==========================================
# 3. 선로 반경 내 건물 필터링 및 엑셀 생성
# ==========================================
def process_spatial_analysis(building_features, rail_features, buffer_distance):
    rail_lines = [LineString(r["pts"]) for r in rail_features if len(r["pts"]) >= 2]
    
    if not rail_lines:
        return [], pd.DataFrame()

    multi_rail = MultiLineString(rail_lines)
    rail_buffer_zone = multi_rail.buffer(buffer_distance)

    filtered_buildings = []
    building_records = []
    bld_idx = 1

    for bld in building_features:
        pts = bld["pts"]
        if len(pts) < 3:
            continue

        try:
            bld_poly = Polygon(pts)
        except Exception:
            continue

        if rail_buffer_zone.intersects(bld_poly):
            centroid_x = bld_poly.centroid.x
            centroid_y = bld_poly.centroid.y
            bld_code = f"BLD-{bld_idx:04d}"

            filtered_buildings.append({
                "code": bld_code,
                "pts": pts,
                "centroid": (centroid_x, centroid_y),
                "poly": bld_poly
            })

            building_records.append({
                "연번": bld_code,
                "건물명": f"건물_{bld_idx}",
                "레이어명": bld["layer"],
                "X좌표(중심)": round(centroid_x, 3),
                "Y좌표(중심)": round(centroid_y, 3),
                "정점수": len(pts),
                "선로이격거리(m)": round(multi_rail.distance(bld_poly), 2),
                "비고": f"선로 반경 {buffer_distance}m 이내"
            })

            bld_idx += 1

    df = pd.DataFrame(building_records)
    return filtered_buildings, df

# ==========================================
# 4. Streamlit UI 구성
# ==========================================
st.set_page_config(page_title="선로 반경 건물 추출기", layout="wide")

st.title("🛤️ 선로 반경 내 건물 영향권 파싱 및 엑셀 추출기")
st.write("선로 반경 안에 위치한 건물만 자동으로 판별하여 연번을 부여하고 씨리얼 양식 엑셀을 생성합니다.")

# 사이드바 설정
st.sidebar.header("⚙️ 분석 설정")
buffer_dist = st.sidebar.number_input("선로 영향 반경 (m)", min_value=1.0, max_value=500.0, value=50.0, step=5.0)

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ 건물 DXF 업로드")
    building_file = st.file_uploader("건물 DXF 파일 선택", type=["dxf"], key="bld_file")

with col2:
    st.subheader("2️⃣ 선로 DXF 업로드")
    rail_file = st.file_uploader("선로 DXF 파일 선택", type=["dxf"], key="rail_file")

if building_file is not None and rail_file is not None:
    # DXF 내부 레이어 자동 감지
    bld_layers = get_dxf_layers(building_file)
    rail_layers = get_dxf_layers(rail_file)

    st.markdown("---")
    st.subheader("🎯 추출할 레이어 지정")
    
    layer_col1, layer_col2 = st.columns(2)
    with layer_col1:
        # '건물'이 포함된 레이어를 기본값으로 자동 선택
        default_bld_idx = next((i for i, l in enumerate(bld_layers) if "건물" in l or "BUILDING" in l.upper()), 0)
        selected_bld_layer = st.selectbox("건물 DXF 레이어 선택", bld_layers, index=default_bld_idx if bld_layers else 0)

    with layer_col2:
        # '선로'가 포함된 레이어를 기본값으로 자동 선택
        default_rail_idx = next((i for i, l in enumerate(rail_layers) if "선로" in l or "RAIL" in l.upper() or "LINE" in l.upper()), 0)
        selected_rail_layer = st.selectbox("선로 DXF 레이어 선택", rail_layers, index=default_rail_idx if rail_layers else 0)

    if st.button("🚀 영향권 건물 파싱 및 엑셀 생성"):
        with st.spinner("DXF 레이어 파싱 및 공간 분석 수행 중..."):
            bld_features = parse_dxf_by_layer(building_file, selected_bld_layer)
            rail_features = parse_dxf_by_layer(rail_file, selected_rail_layer)

        if not bld_features:
            st.error(f"건물 DXF 파일의 '{selected_bld_layer}' 레이어에서 POLYLINE 객체를 찾지 못했습니다.")
        elif not rail_features:
            st.error(f"선로 DXF 파일의 '{selected_rail_layer}' 레이어에서 POLYLINE 객체를 찾지 못했습니다.")
        else:
            filtered_blds, df_buildings = process_spatial_analysis(bld_features, rail_features, buffer_dist)

            st.success(f"분석 완료! 선로 반경 {buffer_dist}m 이내 건물 {len(filtered_blds)}개가 추출되었습니다.")

            # --- Plotly 시각화 ---
            fig = go.Figure()

            # 1. 선로 (빨간색)
            for rail in rail_features:
                rx = [p[0] for p in rail["pts"]]
                ry = [p[1] for p in rail["pts"]]
                fig.add_trace(go.Scatter(
                    x=rx, y=ry, mode='lines',
                    line=dict(color='red', width=3),
                    name='선로'
                ))

            # 2. 건물 (파란색 + 연번 라벨)
            for bld in filtered_blds:
                pts = bld["pts"]
                bx = [p[0] for p in pts] + [pts[0][0]]
                by = [p[1] for p in pts] + [pts[0][1]]

                fig.add_trace(go.Scatter(
                    x=bx, y=by, mode='lines',
                    line=dict(color='blue', width=1.5),
                    fill="toself", fillcolor="rgba(0, 100, 255, 0.2)",
                    showlegend=False, hoverinfo='text',
                    text=f"연번: {bld['code']}"
                ))

                fig.add_trace(go.Scatter(
                    x=[bld["centroid"][0]], y=[bld["centroid"][1]],
                    mode='text', text=[bld["code"]],
                    textposition="middle center",
                    textfont=dict(size=10, color="black"),
                    showlegend=False, hoverinfo='none'
                ))

            fig.update_layout(
                title=f"CAD 오버랩 도면 (선로 반경 {buffer_dist}m 이내 건물 추출)",
                xaxis_title="X 좌표", yaxis_title="Y 좌표",
                yaxis=dict(scaleanchor="x", scaleratio=1),
                width=1000, height=700
            )

            st.plotly_chart(fig, use_container_width=True)

            # --- 엑셀 표 & 다운로드 ---
            st.subheader("📋 씨리얼(SEE:REAL) 건물 정보 데이터")
            st.dataframe(df_buildings, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_buildings.to_excel(writer, index=False, sheet_name='선로반경_건물목록')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 추출된 건물정보 엑셀 파일 다운로드",
                data=excel_data,
                file_name=f"Rail_Buffer_{int(buffer_dist)}m_Buildings.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("💡 건물 DXF 파일과 선로 DXF 파일을 모두 업로드해 주세요.")
