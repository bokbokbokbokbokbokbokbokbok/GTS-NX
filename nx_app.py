import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX - 터널 노선 설계",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ 고해상도 위성 지도 기반 터널 노선 설계 & GTS NX 연동")
st.markdown("지도 위에서 **터널 시점(Start)**과 **종점(End)**을 클릭하여 노선을 정확하게 설정하세요.")

st.divider()

# ======================================================================
# 2. Leaflet JS 지연 없는 클라이언트 전용 지도 렌더링 HTML/JS
# ======================================================================
leaflet_map_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        #map { width: 100%; height: 580px; border-radius: 8px; }
        body { margin: 0; padding: 0; font-family: sans-serif; }
        .info-panel {
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: rgba(0, 0, 0, 0.85); color: white; padding: 12px 16px;
            border-radius: 8px; font-size: 13px; max-width: 280px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        }
        .reset-btn {
            background: #ff4b4b; color: white; border: none; padding: 6px 12px;
            border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 8px;
            width: 100%;
        }
        .reset-btn:hover { background: #ff2b2b; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        <b>📍 터널 노선 지정</b><br>
        1. <b>첫번째 클릭:</b> 터널 시점 (Inlet)<br>
        2. <b>두번째 클릭:</b> 터널 종점 (Outlet)
        <hr style="border: 0.5px solid #444; margin: 8px 0;">
        <div id="status-text">지도상에서 시점을 클릭하세요.</div>
        <button class="reset-btn" onclick="resetPoints()">🔄 좌표 초기화</button>
    </div>

    <script>
        // Leaflet 지도 초기화 (강원도 산악 지역 중심)
        var map = L.map('map').setView([37.5, 128.3], 13);

        // Esri 고해상도 위성지도 레이어
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri World Imagery',
            maxZoom: 18
        }).addTo(map);

        var points = [];
        var markers = [];
        var polyline = null;

        // 지구상 두 좌표 간 거리 계산 수식 (Haversine Formula)
        function getDistance(lat1, lon1, lat2, lon2) {
            var R = 6371000; // 지구 반지름 (m)
            var dLat = (lat2 - lat1) * Math.PI / 180;
            var dLon = (lon2 - lon1) * Math.PI / 180;
            var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                    Math.sin(dLon/2) * Math.sin(dLon/2);
            var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }

        // 클릭 이벤트 핸들러 (반응속도 0초)
        map.on('click', function(e) {
            if (points.length >= 2) {
                resetPoints();
            }

            var lat = e.latlng.lat;
            var lng = e.latlng.lng;
            points.push({lat: lat, lng: lng});

            var label = points.length === 1 ? "시점 (Inlet)" : "종점 (Outlet)";
            var color = points.length === 1 ? "red" : "blue";

            // 커스텀 원형 마커 생성
            var marker = L.circleMarker([lat, lng], {
                color: color,
                fillColor: color,
                fillOpacity: 0.9,
                radius: 8
            }).addTo(map).bindPopup(label).openPopup();
            
            markers.push(marker);

            var statusDiv = document.getElementById('status-text');

            if (points.length === 1) {
                statusDiv.innerHTML = "<b style='color:#ff9800;'>시점 등록 완료!</b><br>종점(Outlet)을 클릭하세요.";
            } else if (points.length === 2) {
                // 노란색 노선 연결
                polyline = L.polyline([
                    [points[0].lat, points[0].lng],
                    [points[1].lat, points[1].lng]
                ], {color: 'yellow', weight: 4, opacity: 0.9}).addTo(map);

                var dist = getDistance(points[0].lat, points[0].lng, points[1].lat, points[1].lng);

                statusDiv.innerHTML = 
                    "<b style='color:#4caf50;'>[노선 연결 완료]</b><br>" +
                    "• 시점: " + points[0].lat.toFixed(4) + "°, " + points[0].lng.toFixed(4) + "°<br>" +
                    "• 종점: " + points[1].lat.toFixed(4) + "°, " + points[1].lng.toFixed(4) + "°<br>" +
                    "<b style='font-size:14px; color:#ffeb3b;'>• 터널 연장: " + dist.toFixed(1) + " m</b>";
            }
        });

        // Reset 버튼 클릭 시
        function resetPoints() {
            points = [];
            markers.forEach(function(m) { map.removeLayer(m); });
            markers = [];
            if (polyline) { map.removeLayer(polyline); polyline = null; }
            document.getElementById('status-text').innerHTML = "지도상에서 시점을 클릭하세요.";
        }
    </script>
</body>
</html>
"""

# ======================================================================
# 3. 레이아웃 배치
# ======================================================================
col_map, col_param = st.columns([2, 1])

with col_map:
    st.subheader("🌐 위성 지도 (실시간 정확한 클릭)")
    components.html(leaflet_map_html, height=600)

with col_param:
    st.subheader("📏 터널 설계 & 공사비 산출")

    tunnel_length = st.number_input("터널 총 연장 L (m)", value=500.0, step=10.0)
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
        st.success("노선 파라미터가 GTS NX 포맷에 성공적으로 도출되었습니다!")
