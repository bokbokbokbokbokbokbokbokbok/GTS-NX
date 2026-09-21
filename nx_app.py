import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ezdxf
import io
from shapely.geometry import LineString, Polygon

st.set_page_config(layout="wide")
st.title("📐 DXF 개별 업로드: 선로 반경 & 건물 연번 오버랩")

# 사이드바: 파일 업로드 및 반경 설정
st.sidebar.header("📁 DXF 파일 업로드")
uploaded_dxf_route = st.sidebar.file_uploader("1. 선로 DXF 파일 업로드", type=["dxf"])
uploaded_dxf_building = st.sidebar.file_uploader("2. 건물 DXF 파일 업로드", type=["dxf"])

buffer_radius = st.sidebar.slider("선로 영향 반경 (m / 단위거리)", min_value=1.0, max_value=50.0, value=10.0, step=1.0)

# -------------------------------------------------------------------
# DXF 읽기 도우미 함수 (DXFStructureError 완벽 방지)
# -------------------------------------------------------------------
def load_dxf_doc(uploaded_file):
    """UploadedFile의 raw bytes를 손상 없이 ezdxf로 로드"""
    raw_bytes = uploaded_file.getvalue()

    # 1. BytesIO로 바이너리/ASCII 직접 로드 시도
    try:
        return ezdxf.read(io.BytesIO(raw_bytes))
    except Exception:
        pass

    # 2. UTF-8 텍스트 스트림 시도
    try:
        text_utf8 = raw_bytes.decode('utf-8', errors='replace')
        return ezdxf.read(io.StringIO(text_utf8))
    except Exception:
        pass

    # 3. EUC-KR / CP949 (한국어 캐드 한글 레이어 대응)
    try:
        text_euckr = raw_bytes.decode('euc-kr', errors='ignore')
        return ezdxf.read(io.StringIO(text_euckr))
    except Exception:
        pass

    # 4. 최후의 수단: latin-1 (바이너리 안전)
    text_latin = raw_bytes.decode('latin-1', errors='ignore')
    return ezdxf.read(io.StringIO(text_latin))

# -------------------------------------------------------------------
# DXF 처리 함수
# -------------------------------------------------------------------

# 1. 선로 DXF 처리 (선로 추출 및 버퍼 연산)
def process_route_dxf(file, buffer_dist):
    doc = load_dxf_doc(file)
    msp = doc.modelspace()
    routes = []
    
    for entity in msp:
        if entity.dxftype() in ['LWPOLYLINE', 'LINE', 'POLYLINE']:
            if entity.dxftype() == 'LINE':
                pts = [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
            else:
                pts = [(p[0], p[1]) for p in entity.get_points()]
            
            x_pts = [p[0] for p in pts]
            y_pts = [p[1] for p in pts]
            
            if len(pts) >= 2:
                line = LineString(pts)
                buffered_line = line.buffer(buffer_dist)
                
                buf_x, buf_y = [], []
                if buffered_line.geom_type == 'Polygon':
                    buf_x, buf_y = buffered_line.exterior.xy
                    buf_x, buf_y = list(buf_x), list(buf_y)
                elif buffered_line.geom_type == 'MultiPolygon':
                    for poly in buffered_line.geoms:
                        bx, by = poly.exterior.xy
                        buf_x.extend(list(bx) + [None])
                        buf_y.extend(list(by) + [None])
                
                routes.append({
                    "x": x_pts,
                    "y": y_pts,
                    "buf_x": buf_x,
                    "buf_y": buf_y
                })
    return routes

# 2. 건물 DXF 처리 (건물 추출 및 중심점/연번 연산)
def process_building_dxf(file):
    doc = load_dxf_doc(file)
    msp = doc.modelspace()
    buildings = []
    
    for entity in msp:
        if entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
            pts = list(entity.vertices()) if entity.dxftype() == 'POLYLINE' else entity.get_points()
            x_pts = [p[0] for p in pts]
            y_pts = [p[1] for p in pts]
            
            # 닫힌 도형 확인
            is_closed = entity.is_closed if hasattr(entity, 'is_closed') else False
            if is_closed or (len(x_pts) > 2 and x_pts[0] == x_pts[-1] and y_pts[0] == y_pts[-1]):
                poly_coords = list(zip(x_pts, y_pts))
                if len(poly_coords) >= 3:
                    try:
                        poly = Polygon(poly_coords)
                        if poly.is_valid and poly.area > 0:
                            centroid = poly.centroid
                            buildings.append({
                                "x": x_pts,
                                "y": y_pts,
                                "center_x": centroid.x,
                                "center_y": centroid.y,
                                "area": poly.area
                            })
                    except Exception:
                        continue
    return buildings

# -------------------------------------------------------------------
# 데이터 처리 및 화면 출력
# -------------------------------------------------------------------

routes = process_route_dxf(uploaded_dxf_route, buffer_radius) if uploaded_dxf_route else []
buildings = process_building_dxf(uploaded_dxf_building) if uploaded_dxf_building else []

# 건물 데이터 연번 부여
b_data = []
for idx, b in enumerate(buildings, start=1):
    b_data.append({
        "연번": idx,
        "중심_X": round(b["center_x"], 2),
        "중심_Y": round(b["center_y"], 2),
        "면적": round(b["area"], 2),
        "raw": b
    })
df_buildings = pd.DataFrame(b_data)

col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("📋 건물대장 연번 목록")
    if not df_buildings.empty:
        selected_no = st.selectbox("🎯 강조 표시할 건물 연번 선택", df_buildings["연번"].tolist())
        st.dataframe(
            df_buildings[["연번", "면적", "중심_X", "중심_Y"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        selected_no = None
        st.info("👈 사이드바에서 건물 DXF 파일을 업로드해 주세요.")

with col2:
    st.subheader("🖥️ CAD 통합 오버랩 화면")
    fig = go.Figure()

    # [1] 선로 및 반경 표시
    for r in routes:
        if r["buf_x"]:
            fig.add_trace(go.Scatter(
                x=r["buf_x"], y=r["buf_y"],
                fill="toself",
                fillcolor="rgba(16, 185, 129, 0.2)",
                line=dict(color="rgba(16, 185, 129, 0.4)", width=1),
                name="선로 영향 반경",
                hoverinfo="skip",
                showlegend=False
            ))
        fig.add_trace(go.Scatter(
            x=r["x"], y=r["y"],
            mode="lines",
            line=dict(color="#059669", width=3),
            name="선로"
        ))

    # [2] 건물 및 연번 표시
    for item in b_data:
        b_no = item["연번"]
        b_info = item["raw"]
        is_selected = (b_no == selected_no)

        fig.add_trace(go.Scatter(
            x=b_info["x"], y=b_info["y"],
            fill="toself",
            fillcolor="rgba(239, 68, 68, 0.4)" if is_selected else "rgba(59, 130, 246, 0.2)",
            line=dict(
                color="red" if is_selected else "#2563EB",
                width=3 if is_selected else 1.5
            ),
            showlegend=False,
            hoverinfo="text",
            hovertext=f"건물 연번: No.{b_no}"
        ))

        # 건물 중심에 연번 표기
        fig.add_trace(go.Scatter(
            x=[b_info["center_x"]],
            y=[b_info["center_y"]],
            mode="text",
            text=[f"<b>[{b_no}]</b>"],
            textposition="middle center",
            textfont=dict(
                size=14 if is_selected else 11,
                color="red" if is_selected else "#1E293B"
            ),
            showlegend=False,
            hoverinfo="skip"
        ))

    fig.update_layout(
        xaxis=dict(showgrid=True, zeroline=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(showgrid=True, zeroline=False),
        plot_bgcolor="#F8FAFC",
        height=600,
        dragmode="pan"
    )

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
