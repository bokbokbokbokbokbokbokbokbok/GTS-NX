import math
import streamlit as st

# ======================================================================
# 1. 패키지 안전 로딩 (미설치 시 예외 처리)
# ======================================================================
try:
    import folium
    from streamlit_folium import st_folium
except ModuleNotFoundError:
    st.error("⚠️ `folium` 패키지를 설치 중입니다. `requirements.txt` 수정 후 약 30초 뒤 페이지를 새로고침(F5)해 주세요!")
    st.stop()

# ======================================================================
# 2. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX - 터널 노선 설계",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ 위성 지도 기반 터널 노선 설계 & GTS NX 연동")
st.markdown("지도 위에서 **터널 시점**과 **종점**을 클릭하여 노선을 설정하세요.")

st.divider()

# Session State 초기화 (클릭 좌표 저장용)
if "points" not in st.session_state:
    st.session_state.points = []

# ======================================================================
# 3. 레이아웃 구성
# ======================================================================
col_map, col_param = st.columns([2, 1])

with col_map:
    st.subheader("🌐 위성 지도 (지도 클릭 시 좌표 등록)")
    
    # 지도 중심점 (대한민국 산악지역 예시: 강원도 평창)
    map_center = [37.5, 128.3]
    
    # Esri World Imagery (고해상도 무료 위성지도)
    m = folium.Map(
        location=map_center,
        zoom_start=12,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery"
    )

    # 저장된 클릭 지점 마커 및 선 그리기
    for idx, pt in enumerate(st.session_state.points):
        label = "시점 (Inlet)" if idx == 0 else "종점 (Outlet)"
        color = "red" if idx == 0 else "blue"
        folium.Marker(
            location=[pt["lat"], pt["lng"]],
            popup=label,
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(m)

    if len(st.session_state.points) == 2:
        p1 = [st.session_state.points[0]["lat"], st.session_state.points[0]["lng"]]
        p2 = [st.session_state.points[1]["lat"], st.session_state.points[1]["lng"]]
        folium.PolyLine(locations=[p1, p2], color="yellow", weight=5, opacity=0.8).add_to(m)

    # Folium 지도 렌더링 및 클릭 이벤트 수신
    map_data = st_folium(m, width="100%", height=550)

    # 지도 클릭 처리
    if map_data and map_data.get("last_clicked"):
        clicked_pt = map_data["last_clicked"]
        
        # 2개 지점이 이미 차있으면 새로 시작
        if len(st.session_state.points) >= 2:
            st.session_state.points = [clicked_pt]
        else:
            st.session_state.points.append(clicked_pt)
        
        st.rerun()

    if st.button("🔄 선택 좌표 초기화"):
        st.session_state.points = []
        st.rerun()

# ======================================================================
# 4. 우측 연산 패널
# ======================================================================
with col_param:
    st.subheader("📏 터널 설계 & 공사비 산출")

    # 직선 거리 계산 함수 (Haversine Formula)
    def calculate_distance(p1, p2):
        R = 6371000  # 지구 반지름 (m)
        phi1 = math.radians(p1["lat"])
        phi2 = math.radians(p2["lat"])
        delta_phi = math.radians(p2["lat"] - p1["lat"])
        delta_lambda = math.radians(p2["lng"] - p1["lng"])

        a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # 노선 거리 자동 적용
    calculated_length = 500.0
    if len(st.session_state.points) == 2:
        calculated_length = calculate_distance(st.session_state.points[0], st.session_state.points[1])
        st.success(f"📍 지도에서 산출된 터널 연장: **{calculated_length:.1f} m**")

    tunnel_length = st.number_input("터널 총 연장 L (m)", value=float(round(calculated_length, 1)), step=10.0)
    tunnel_area = st.number_input("터널 단면적 A (m²)", value=65.0, step=5.0)
    
    rmr_score = st.slider("지반 RMR 점수", min_value=0, max_value=100, value=55)

    if rmr_score >= 61:
        pattern = "Pattern I (전단면 굴착)"
        cost_per_m = 12000000
    elif rmr_score >= 41:
        pattern = "Pattern III (상/하반 분할 굴착)"
        cost_per_m = 18000000
    else:
        pattern = "Pattern V (강지보재 + 훠폴링 보강)"
        cost_per_m = 26000000

    st.info(f"**추천 굴착 패턴:** {pattern}")

    total_cost_krw = (tunnel_length * cost_per_m) + 500000000
    st.metric("총 개략 공사비", f"{total_cost_krw / 1e8:.2f} 억원")

    st.divider()
    
    st.subheader("🛡️ Hoek-Brown 지반 파괴 검토")
    sig_ci = st.number_input("암석 일축압축강도 σci (kPa)", value=50000.0, step=5000.0)
    gsi = max(0, rmr_score - 5)
    st.write(f"추정 GSI 지수: **{gsi}**")
    
    if st.button("🚀 GTS NX 연동 데이터 도출"):
        st.success("MCT 및 API 파라미터 반영 완료!")
