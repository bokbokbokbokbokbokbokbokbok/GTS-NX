import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import Polygon, LineString, MultiLineString
from pyproj import Transformer
import io
import tempfile
import os

# ==========================================
# 1. DXF 복구 및 안전 로드 함수
# ==========================================
def load_dxf_document(file_input):
    file_input.seek(0)
    bytes_data = file_input.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
        tmp_file.write(bytes_data)
        tmp_path = tmp_file.name

    try:
        doc, auditor = recover.readfile(tmp_path)
        os.remove(tmp_path)
        return doc
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    try:
        return ezdxf.read(io.BytesIO(bytes_data))
    except Exception:
        pass

    for encoding in ['cp949', 'euc-kr', 'ansi', 'utf-8']:
        try:
            text_data = bytes_data.decode(encoding, errors='ignore')
            return ezdxf.read(io.StringIO(text_data))
        except Exception:
            continue

    raise ValueError("DXF 파일 파싱 실패: 파일이 손상되었거나 인코딩이 지원되지 않습니다.")

# ==========================================
# 2. DXF 레이어 목록 추출
# ==========================================
def get_dxf_layers(file_input):
    try:
        doc = load_dxf_document(file_input)
        layers = [layer.dxf.name for layer in doc.layers]
        return sorted(layers)
    except Exception as e:
        st.error(f"DXF 레이어 읽기 오류 ({file_input.name}): {e}")
        return []

# ==========================================
# 3. DXF 레이어별 객체 파싱
# ==========================================
def parse_dxf_by_layer(file_input, target_layer_name):
    try:
        doc = load_dxf_document(file_input)
    except Exception as e:
        st.error(f"DXF 파일 읽기 오류 ({file_input.name}): {e}")
        return []

    msp = doc.modelspace()
    features = []

    for entity in msp:
        layer_name = entity.dxf.layer if hasattr(entity.dxf, 'layer') else ""
        if target_layer_name.strip().lower() != layer_name.strip().lower():
            continue

        dxf_type = entity.dxftype()
        pts = []

        if dxf_type == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        elif dxf_type == 'LWPOLYLINE':
            raw_pts = entity.get_points()
            pts = [(p[0], p[1]) for p in raw_pts]
        elif dxf_type == 'LINE':
            pts = [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]

        if len(pts) >= 2:
            features.append({
                "layer": layer_name,
                "type": dxf_type,
                "pts": pts
            })

    return features

# ==========================================
# 4. 공간 분석 및 버퍼 판정 (숫자 연번 순차 부여)
# ==========================================
def process_spatial_analysis(building_features, rail_features, buffer_distance):
    rail_lines = [LineString(r["pts"]) for r in rail_features if len(r["pts"]) >= 2]
    if not rail_lines:
        return [], pd.DataFrame(), None

    multi_rail = MultiLineString(rail_lines)
    rail_buffer_zone = multi_rail.buffer(buffer_distance)

    filtered_buildings = []
    building_records = []
    bld_idx = 1  # 1부터 시작하는 숫자 연번

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
            bld_code = str(bld_idx)  # 숫자 연번 (1, 2, 3...)

            filtered_buildings.append({
                "code": bld_code,
                "pts": pts,
                "centroid": (centroid_x, centroid_y),
                "poly": bld_poly
            })

            building_records.append({
                "연번": bld_idx,
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
    return filtered_buildings, df, rail_buffer_zone

# ==========================================
# 5. UI 및 Streamlit 메인 구성
# ==========================================
st.set_page_config(page_title="선로-건물-지도 3D 오버랩 검토기", layout="wide")

st.title("🗺️ 3중 오버랩 기반 선로 영향권 건물 분석 시스템")
st.write("선로 CAD, 건물 CAD, 씨리얼/공공 지도를 좌표 기반으로 정밀 오버랩하여 마우스로 자유롭게 이동 및 확대한 후 연번(1, 2, 3...)을 비교합니다.")

st.sidebar.header("⚙️ 좌표계 및 분석 설정")
epsg_code = st.sidebar.selectbox(
    "CAD 도면 좌표계 선택 (KOREA EPSG)",
    ["EPSG:5186 (중부원점 GR380)", "EPSG:5181 (중부원점 Bessel)", "EPSG:5179 (UTM-K 신좌표계)"],
    index=0
)
epsg_num = epsg_code.split()[0]

buffer_dist = st.sidebar.number_input("선로 영향 반경 (m)", min_value=1.0, max_value=500.0, value=50.0, step=5.0)

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ 건물 CAD (DXF)")
    building_file = st.file_uploader("건물 DXF 업로드", type=["dxf"], key="bld_file")

with col2:
    st.subheader("2️⃣ 선로 CAD (DXF)")
    rail_file = st.file_uploader("선로 DXF 업로드", type=["dxf"], key="rail_file")

if building_file and rail_file:
    bld_layers = get_dxf_layers(building_file)
    rail_layers = get_dxf_layers(rail_file)

    st.markdown("---")
    st.subheader("🎯 추출 레이어 설정")
    lcol1, lcol2 = st.columns(2)
    
    with lcol1:
        selected_bld_layer = st.selectbox("건물 레이어", bld_layers)
    with lcol2:
        selected_rail_layer = st.selectbox("선로 레이어", rail_layers)

    if st.button("🚀 3중 오버랩 지도 시각화 및 건물 연번 추출"):
        with st.spinner("CAD 좌표 투영 및 지도 오버랩 분석 중..."):
            bld_features = parse_dxf_by_layer(building_file, selected_bld_layer)
            rail_features = parse_dxf_by_layer(rail_file, selected_rail_layer)

            filtered_blds, df_buildings, buffer_zone = process_spatial_analysis(bld_features, rail_features, buffer_dist)

            # 좌표 변환기 (CAD 투영좌표계 -> 위도/경도 WGS84)
            transformer = Transformer.from_crs(epsg_num, "EPSG:4326", always_xy=True)

            fig = go.Figure()

            # 1. 선로 CAD 레이어 오버랩 (빨간색)
            for rail in rail_features:
                rx_list, ry_list = [], []
                for p in rail["pts"]:
                    lon, lat = transformer.transform(p[0], p[1])
                    rx_list.append(lon)
                    ry_list.append(lat)

                fig.add_trace(go.Scattermapbox(
                    lon=rx_list, lat=ry_list,
                    mode='lines',
                    line=dict(width=4, color='red'),
                    name='선로 CAD'
                ))

            # 2. 반경 내 영향권 건물 CAD 레이어 오버랩 (파란색 + 숫자 연번 표시)
            center_lats, center_lons = [], []
            for bld in filtered_blds:
                bx_list, by_list = [], []
                pts = bld["pts"] + [bld["pts"][0]] # 닫힌 다각형
                
                for p in pts:
                    lon, lat = transformer.transform(p[0], p[1])
                    bx_list.append(lon)
                    by_list.append(lat)

                fig.add_trace(go.Scattermapbox(
                    lon=bx_list, lat=by_list,
                    mode='lines',
                    fill='toself',
                    fillcolor='rgba(0, 120, 255, 0.35)',
                    line=dict(width=2, color='blue'),
                    hoverinfo='text',
                    text=f"건물 연번: {bld['code']}",
                    showlegend=False
                ))

                # 건물 중심 좌표에 숫자 연번 마커 추가
                c_lon, c_lat = transformer.transform(bld["centroid"][0], bld["centroid"][1])
                center_lons.append(c_lon)
                center_lats.append(c_lat)

                fig.add_trace(go.Scattermapbox(
                    lon=[c_lon], lat=[c_lat],
                    mode='text',
                    text=[bld["code"]],
                    textfont=dict(size=14, color='black'),
                    hoverinfo='none',
                    showlegend=False
                ))

            # 지도 중심점 계산
            if center_lats:
                avg_lat = sum(center_lats) / len(center_lats)
                avg_lon = sum(center_lons) / len(center_lons)
            else:
                avg_lat, avg_lon = 37.5665, 126.9780

            # 3. 씨리얼 / OpenStreetMap 오버랩 레이아웃
            fig.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    center=dict(lat=avg_lat, lon=avg_lon),
                    zoom=15
                ),
                margin=dict(l=0, r=0, t=30, b=0),
                height=750,
                title=f"📌 선로 반경 {buffer_dist}m 오버랩 지도 (마우스 드래그/휠 확대 이동 가능)"
            )

            st.plotly_chart(fig, use_container_width=True)

            # 표 및 엑셀 출력
            st.subheader("📋 선로 영향권 건물 연번 비교 데이터 (씨리얼 양식)")
            st.dataframe(df_buildings, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_buildings.to_excel(writer, index=False, sheet_name='영향권건물_목록')
            
            st.download_button(
                label="📥 연번 매칭 건물목록 엑셀 다운로드",
                data=output.getvalue(),
                file_name=f"Rail_Overlap_Buildings_{int(buffer_dist)}m.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("💡 선로 및 건물 CAD(DXF) 파일 2개를 모두 업로드하면 3중 오버랩 지도가 표시됩니다.")
