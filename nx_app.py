import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ezdxf  # 실제 DXF 파싱 시 사용

st.set_page_config(layout="wide")
st.title("📐 CAD 오버랩 분석: 과업 선로 & 건물 수치지도")

# -------------------------------------------------------------------
# 1. 건물대장 데이터 및 수치지도 샘플 데이터 (실제 DXF 추출 데이터 대체 가능)
# -------------------------------------------------------------------

# 건물대장 목록 데이터
building_info = [
    {"연번": 1, "건물명": "본관 A동", "층수": "지상 5층", "용도": "업무시설", "X": 100, "Y": 200},
    {"연번": 2, "건물명": "연구동 B동", "층수": "지상 3층", "용도": "교육연구시설", "X": 250, "Y": 300},
    {"연번": 3, "건물명": "창고 C동", "층수": "지상 1층", "용도": "창고시설", "X": 180, "Y": 120},
    {"연번": 4, "건물명": "기숙사 D동", "층수": "지상 4층", "용도": "공동주택", "X": 320, "Y": 180},
]
df_buildings = pd.DataFrame(building_info)

# [CAD Base 1] 건물 수치지도 다각형(Polygon) 좌표 예시
cad_buildings_polygons = [
    # (연번, X좌표 리스트, Y좌표 리스트)
    (1, [80, 120, 120, 80, 80], [180, 180, 220, 220, 180]),
    (2, [220, 280, 280, 220, 220], [280, 280, 320, 320, 280]),
    (3, [160, 200, 200, 160, 160], [100, 100, 140, 140, 100]),
    (4, [300, 340, 340, 300, 300], [160, 160, 200, 200, 160]),
]

# [CAD Base 2] 과업 진행 선로 좌표 예시
cad_work_line = {
    "X": [50, 100, 180, 250, 320, 380],
    "Y": [150, 200, 120, 300, 180, 220]
}

# -------------------------------------------------------------------
# 2. 화면 화면 구성 (좌: 건물대장 표 / 우: CAD 오버랩 시각화)
# -------------------------------------------------------------------

col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("📋 건물대장 정보 목록")
    
    # 강조할 연번 선택
    selected_no = st.selectbox("🔍 지도에서 강조하여 비교할 건물 연번 선택", df_buildings["연번"].tolist())
    
    # 데이터프레임 표시
    st.dataframe(
        df_buildings[["연번", "건물명", "용도", "층수"]],
        use_container_width=True,
        hide_index=True
    )
    
    # 선택된 건물 상세 정보 표기
    selected_row = df_buildings[df_buildings["연번"] == selected_no].iloc[0]
    st.info(f"**[선택된 건물 정보]**\n- **연번**: {selected_row['연번']}번\n- **건물명**: {selected_row['건물명']}\n- **용도**: {selected_row['용도']} ({selected_row['층수']})")

with col2:
    st.subheader("🖥️ CAD 오버랩 화면 (인터넷 지도 없음)")
    
    fig = go.Figure()

    # 1 LAYER: [CAD 1] 건물 수치지도 (Polygon) 그리기
    for b_no, x_pts, y_pts in cad_buildings_polygons:
        is_selected = (b_no == selected_no)
        
        fig.add_trace(go.Scatter(
            x=x_pts,
            y=y_pts,
            fill="toself",
            fillcolor="rgba(239, 68, 68, 0.4)" if is_selected else "rgba(59, 130, 246, 0.2)",
            line=dict(
                color="red" if is_selected else "#2563EB",
                width=3 if is_selected else 1.5
            ),
            name=f"건물 (No.{b_no})",
            hoverinfo="text",
            hovertext=f"건물 연번: No.{b_no}",
            showlegend=False
        ))

    # 2 LAYER: [CAD 2] 과업 진행 선로 (Line) 그리기
    fig.add_trace(go.Scatter(
        x=cad_work_line["X"],
        y=cad_work_line["Y"],
        mode="lines+markers",
        line=dict(color="#10B981", width=3, dash="dash"),
        marker=dict(size=6, color="#047857"),
        name="과업 진행 선로",
        hoverinfo="text",
        hovertext="과업 진행 선로 구간"
    ))

    # 3 LAYER: 건물 중앙에 [연번 번호 표기]
    for _, row in df_buildings.iterrows():
        b_no = row["연번"]
        is_selected = (b_no == selected_no)
        
        fig.add_trace(go.Scatter(
            x=[row["X"]],
            y=[row["Y"]],
            mode="text",
            text=[f"<b>[{b_no}]</b>"],
            textposition="middle center",
            textfont=dict(
                size=14 if is_selected else 11,
                color="red" if is_selected else "#1E293B"
            ),
            hoverinfo="text",
            hovertext=f"No.{b_no} {row['건물명']}",
            showlegend=False
        ))

    # 차트 레이아웃 설정 (배경을 깔끔한 모눈종이/백지 형태로 설정, 비율 유지)
    fig.update_layout(
        xaxis=dict(showgrid=True, zeroline=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(showgrid=True, zeroline=False),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=30, b=20),
        height=550,
        dragmode="pan",  # 기본 마우스 동작을 이동(Pan)으로 설정
        legend=dict(x=0.02, y=0.98, bgcolor="rgba(255,255,255,0.8)")
    )

    # Plotly 차트 출력 (마우스 휠 조작 활성화)
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
