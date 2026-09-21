import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ezdxf
from shapely.geometry import LineString, Polygon

st.set_page_config(layout="wide")
st.title("📐 DXF 레이어 인식: 선로 반경 & 건물 연번 오버랩")

# 사이드바 컨트롤
st.sidebar.header("⚙️ 설정 및 파일 업로드")
uploaded_dxf = st.sidebar.file_uploader("DXF 파일 업로드", type=["dxf"])
buffer_radius = st.sidebar.slider("선로 영향 반경 (m / 단위거리)", min_value=1.0, max_value=50.0, value=10.0, step=1.0)

# -------------------------------------------------------------------
# DXF 파싱 함수
# -------------------------------------------------------------------
def process_dxf(file, buffer_dist):
    doc = ezdxf.readfile_line_ending_fix(file)
    msp = doc.modelspace()
    
    buildings = []
    routes = []
    
    for entity in msp:
        layer_name = entity.dxf.layer.strip()
        
        # 1. "건물" 레이어 추출
        if "건물" in layer_name:
            if entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
                pts = list(entity.vertices()) if entity.dxftype() == 'POLYLINE' else entity.get_points()
                x_pts = [p[0] for p in pts]
                y_pts = [p[1] for p in pts]
                
                # 닫힌 도형 생성
                if entity.is_closed or (x_pts[0] == x_pts[-1] and y_pts[0] == y_pts[-1]):
                    poly_coords = list(zip(x_pts, y_pts))
                    if len(poly_coords) >= 3:
                        poly = Polygon(poly_coords)
                        centroid = poly.centroid
                        buildings.append({
                            "x": x_pts,
                            "y": y_pts,
                            "center_x": centroid.x,
                            "center_y": centroid.y,
                            "area": poly.area
                        })

        # 2. "선로" 레이어 추출
        elif "선로" in layer_name:
            if entity.dxftype() in ['LWPOLYLINE', 'LINE', 'POLYLINE']:
                if entity.dxftype() == 'LINE':
                    pts = [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
                else:
                    pts = [(p[0], p[1]) for p in entity.get_points()]
                
                x_pts = [p[0] for p in pts]
                y_pts = [p[1] for p in pts]
                
                # 선로 반경(버퍼) 연산
                if len(pts) >= 2:
                    line = LineString(pts)
                    buffered_line = line.buffer(buffer_dist)
                    
                    buf_x, buf_y = [], []
                    if buffered_line.geom_type == 'Polygon':
                        buf_x, buf_y = buffered_line.exterior.xy
                        buf_x, buf_y = list(buf_x), list(buf_y)
                    
                    routes.append({
                        "x": x_pts,
                        "y": y_pts,
                        "buf_x": buf_x,
                        "buf_y": buf_y
                    })
                    
    return buildings, routes

# -------------------------------------------------------------------
# 데이터 수집 및 화면 구성
# -------------------------------------------------------------------
if uploaded_dxf:
    buildings, routes = process_dxf(uploaded_dxf, buffer_radius)
    
    # 건물 데이터 프레임 생성 (연번 부여)
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
        selected_no = st.selectbox("🎯 위치를 확인할 건물 연번 선택", df_buildings["연번"].tolist() if not df_buildings.empty else [None])
        
        st.dataframe(
            df_buildings[["연번", "면적", "중심_X", "중심_Y"]],
            use_container_width=True,
            hide_index=True
        )

    with col2:
        st.subheader(f"🖥️ CAD 시각화 (선로 반경 {buffer_radius}m 적용)")
        fig = go.Figure()

        # [1] "선로" 레이어 및 반경(Buffer) 그리기
        for r in routes:
            # 반경 영역 (Polygon)
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
            # 중심 선로 (Line)
            fig.add_trace(go.Scatter(
                x=r["x"], y=r["y"],
                mode="lines",
                line=dict(color="#059669", width=3),
                name="선로 레이어"
            ))

        # [2] "건물" 레이어 그리기
        for item in b_data:
            b_no = item["연번"]
            b_info = item["raw"]
            is_selected = (b_no == selected_no)

            # 건물 외곽선
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

            # 건물 중앙에 [연번] 텍스트 표기
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

        # 차트 비율 및 레이아웃
        fig.update_layout(
            xaxis=dict(showgrid=True, zeroline=False, scaleanchor="y", scaleratio=1),
            yaxis=dict(showgrid=True, zeroline=False),
            plot_bgcolor="#F8FAFC",
            height=600,
            dragmode="pan"
        )

        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

else:
    st.info("👈 왼쪽 사이드바에서 '건물' 및 '선로' 레이어가 포함된 **DXF 파일**을 업로드해 주세요.")
