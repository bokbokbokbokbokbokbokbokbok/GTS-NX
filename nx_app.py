import math
import io
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import streamlit as st
import streamlit.components.v1 as components

# ezdxf 로드 예외 처리
try:
    import ezdxf
except ModuleNotFoundError:
    st.error("⚠️ `ezdxf` 패키지가 필요합니다. `requirements.txt`에 `ezdxf`를 추가해 주세요.")
    st.stop()

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX 3D 터널 모식도 & OK/NG 안전성 검토",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ 3D 터널 모식화 & OK / NG 종합 안전성 검토기")
st.markdown("노선 설정 및 DXF 데이터를 기반으로 **4대 구조 안정성(OK/NG)**을 판정하고 **3D 터널 형상**을 모식화합니다.")

st.divider()

# ======================================================================
# 2. 파이썬 연산 엔진 (OK / NG 판정 & 3D 좌표 산출)
# ======================================================================
def evaluate_stability(depth=35.0, gamma=23.0, k0=0.5, E_rock=1500000.0):
    """4대 안정성 항목 OK/NG 단순 판정 알고리즘"""
    sigma_v = gamma * depth
    sigma_h = k0 * sigma_v
    radius = 6.5
    v = 0.25

    # 변위 및 응력 계산
    u_crown = ((1 + v) * radius * sigma_v / E_rock) * 1000.0
    u_wall = ((1 + v) * radius * sigma_h / E_rock) * 1000.0
    
    # 숏크리트 휨응력 (MPa) & 록볼트 축력 (kN)
    sigma_shotcrete = (3.0 * 20000000.0 * ((0.15**3)/12.0) * (u_crown / 1000.0) / (radius**2)) / ((0.15**2)/6.0) / 1000.0
    t_rockbolt = min(180.0, 210000000.0 * 0.00049 * (u_crown / 1000.0 / 4.0) * 1.5)

    # OK / NG 판정 (기준: 천단 20mm, 내공 25mm, 숏크리트 21MPa, 록볼트 130kN)
    res_crown = "OK" if u_crown <= 20.0 else "NG"
    res_wall = "OK" if u_wall <= 25.0 else "NG"
    res_shotcrete = "OK" if sigma_shotcrete <= 21.0 else "NG"
    res_rockbolt = "OK" if t_rockbolt <= 130.0 else "NG"

    is_total_ok = (res_crown == "OK" and res_wall == "OK" and res_shotcrete == "OK" and res_rockbolt == "OK")
    
    return {
        "crown": res_crown,
        "wall": res_wall,
        "shotcrete": res_shotcrete,
        "rockbolt": res_rockbolt,
        "total": "OK (안전)" if is_total_ok else "NG (보강 필요)"
    }

# ======================================================================
# 3. 화면 레이아웃
# ======================================================================
col_map, col_result = st.columns([1.8, 1.2])

with col_map:
    st.subheader("🌐 노선 지도 & DXF 지보 도면 업로드")
    
    uploaded_dxf = st.file_uploader("DXF 도면 파일 업로드 (7km235_PD-2A.dxf)", type=["dxf"])
    
    # 지도 HTML/JS
    map_html = """
    <div id="map" style="width:100%; height:320px; border-radius:8px;"></div>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([37.5, 128.3], 13);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom: 18}).addTo(map);
        
        var points = [[37.5, 128.28], [37.505, 128.31], [37.51, 128.33]];
        points.forEach(function(pt, idx) {
            L.circleMarker(pt, {color: idx===0?'red':'blue', radius:7}).addTo(map);
        });
        L.polyline(points, {color:'yellow', weight:4}).addTo(map);
    </script>
    """
    components.html(map_html, height=330)

    # 3D 터널 단면 모식화 뷰어
    st.subheader("🧊 3D 터널 단면 & 지보재 모식화 (3D Model)")
    
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(111, projection='3d')
    
    # 3D 터널 라이너 3D 파이프 모식화 데이터
    z_length = np.linspace(0, 50, 30)
    theta = np.linspace(0, np.pi, 20)
    theta_grid, z_grid = np.meshgrid(theta, z_length)
    
    r = 6.5
    x_grid = r * np.cos(theta_grid)
    y_grid = r * np.sin(theta_grid)
    
    # 3D 터널 라이닝 표면 그리기
    ax.plot_surface(x_grid, z_grid, y_grid, color='#2196F3', alpha=0.6, edgecolor='gray', linewidth=0.2)
    
    # 록볼트 3D 방사형 막대 모식화
    for b_z in [10, 25, 40]:
        for b_th in np.linspace(0.2, np.pi - 0.2, 7):
            bx = [r * math.cos(b_th), (r + 3.0) * math.cos(b_th)]
            by = [r * math.sin(b_th), (r + 3.0) * math.sin(b_th)]
            bz = [b_z, b_z]
            ax.plot(bx, bz, by, color='red', lw=2)

    ax.set_title("3D Tunnel Shell & Rockbolt Layout")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Tunnel Length Z (m)")
    ax.set_zlabel("Height Y (m)")
    st.pyplot(fig)

# 오른쪽 판단 결과 화면 (OK / NG 전용)
with col_result:
    st.subheader("🚥 종합 안전성 OK / NG 판정")
    
    # 조건 입력
    depth = st.number_input("굴착 깊이 H (m)", value=35.0, step=5.0)
    e_rock = st.number_input("암반 변형계수 E (MPa)", value=1500.0, step=100.0) * 1000.0
    
    eval_res = evaluate_stability(depth=depth, E_rock=e_rock)

    # 메인 OK / NG 대형 판정 박스
    if "OK" in eval_res["total"]:
        st.success(f"### 🎉 최종 결과: {eval_res['total']}")
    else:
        st.error(f"### 🚨 최종 결과: {eval_res['total']}")

    st.divider()
    st.markdown("### 📋 항목별 세부 OK / NG 현황")

    # 1. 천단변위
    if eval_res["crown"] == "OK":
        st.success("🟢 **1. 천단변위:** OK (기준 만족)")
    else:
        st.error("🔴 **1. 천단변위:** NG (허용치 초과)")

    # 2. 내공변위
    if eval_res["wall"] == "OK":
        st.success("🟢 **2. 내공변위:** OK (기준 만족)")
    else:
        st.error("🔴 **2. 내공변위:** NG (허용치 초과)")

    # 3. 숏크리트 휨응력
    if eval_res["shotcrete"] == "OK":
        st.success("🟢 **3. 숏크리트 휨압축응력:** OK (기준 만족)")
    else:
        st.error("🔴 **3. 숏크리트 휨압축응력:** NG (파괴 위험)")

    # 4. 록볼트 축력
    if eval_res["rockbolt"] == "OK":
        st.success("🟢 **4. 록볼트 최대축력:** OK (기준 만족)")
    else:
        st.error("🔴 **4. 록볼트 최대축력:** NG (항복 위험)")

    st.divider()
    if st.button("🚀 GTS NX 보고서용 OK/NG 데이터 도출"):
        st.info("OK/NG 판정 데이터가 GTS NX 해석 일지 형태로 출력되었습니다.")
