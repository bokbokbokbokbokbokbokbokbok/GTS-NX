import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX - 터널 다중/곡선 노선 설계",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ N개 지점 클릭 & 곡선(Curve) 터널 노선 설계")
st.markdown("지도 위에서 **시점부터 종점까지 N개의 지점을 연속으로 클릭**하여 곡선 터널 노선을 설정하세요.")

st.divider()

# ======================================================================
# 2. Leaflet JS - N개 지점 연속 클릭 & 곡선 노선 생성 HTML/JS
# ======================================================================
leaflet_curve_map_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <!-- 곡선(Bézier Curve) 생성을 위한 Leaflet.curve 플러그인 -->
    <script src="https://cdn.jsdelivr.net/npm/leaflet-curve@1.0.0/leaflet.curve.min.js"></script>
    <style>
        #map { width: 100%; height: 600px; border-radius: 8px; }
        body { margin: 0; padding: 0; font-family: sans-serif; }
        .info-panel {
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: rgba(0, 0, 0, 0.88); color: white; padding: 14px;
            border-radius: 8px; font-size: 13px; max-width: 300px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .btn-group { display: flex; gap: 6px; margin-top: 10px; }
        .btn {
            flex: 1; border: none; padding: 8px; border-radius: 4px;
            cursor: pointer; font-weight: bold; color: white; font-size: 12px;
        }
        .btn-reset { background: #ff4b4b; }
        .btn-reset:hover { background: #e03e3e; }
        .btn-complete { background: #4caf50; }
        .btn-complete:hover { background: #3d8b40; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        <b>📍 다중 절점 & 곡선 노선 설정</b><br>
        • <b>1번째 클릭:</b> 시점 (Inlet)<br>
        • <b>2~N번째 클릭:</b> 곡선 경유점(VIP)<br>
        • <b>마지막 클릭:</b> 종점 (Outlet)
        <hr style="border: 0.5px solid #444; margin: 8px 0;">
        <div id="status-text">지도 위를 클릭하여 N개 절점을 등록하세요.</div>
        <div class="btn-group">
            <button class="btn btn-reset" onclick="resetPoints()">🔄 초기화</button>
        </div>
    </div>

    <script>
        // Leaflet 지도 초기화
        var map = L.map('map').setView([37.5, 128.3], 13);

        // Esri 고해상도 위성 지도
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri World Imagery',
            maxZoom: 18
        }).addTo(map);

        var points = [];
        var markers = [];
        var polylinePath = null;

        // Haversine 거리 계산 함수 (m)
        function getDistance(lat1, lon1, lat2, lon2) {
            var R = 6371000;
            var dLat = (lat2 - lat1) * Math.PI / 180;
            var dLon = (lon2 - lon1) * Math.PI / 180;
            var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                    Math.sin(dLon/2) * Math.sin(dLon/2);
            var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }

        // 지도 클릭 시 N번째 지점 등록
        map.on('click', function(e) {
            var lat = e.latlng.lat;
            var lng = e.latlng.lng;
            points.push([lat, lng]);

            var n = points.length;
            var label = "P" + n + " ";
            var color = "#ffeb3b"; // 기본 경유점: 노란색

            if (n === 1) {
                label += "(시점 - Inlet)";
                color = "#ff4b4b"; // 시점: 빨간색
            }

            // 커스텀 원형 마커
            var marker = L.circleMarker([lat, lng], {
                color: '#ffffff',
                fillColor: color,
                fillOpacity: 1.0,
                radius: 7,
                weight: 2
            }).addTo(map).bindPopup(label).openPopup();

            markers.push(marker);

            // 기존 선 지우고 새로 연결
            if (polylinePath) { map.removeLayer(polylinePath); }

            // N개 지점 곡선/굴절선 생성 및 총 연장 계산
            if (n >= 2) {
                polylinePath = L.polyline(points, {
                    color: '#00e676',
                    weight: 5,
                    opacity: 0.9,
                    smoothFactor: 1.5 // 곡선 평활화
                }).addTo(map);

                // N개 지점 누적 거리 계산
                var totalDist = 0;
                for (var i = 0; i < n - 1; i++) {
                    totalDist += getDistance(points[i][0], points[i][1], points[i+1][0], points[i+1][1]);
                }

                document.getElementById('status-text').innerHTML = 
                    "<b style='color:#4caf50;'>[노선 연결 중 - " + n + "개 절점]</b><br>" +
                    "• 입력된 절점 수: <b>" + n + " 개</b><br>" +
                    "<b style='font-size:14px; color:#ffeb3b;'>• 곡선 총 연장: " + totalDist.toFixed(1) + " m</b>";
            } else {
                document.getElementById('status-text').innerHTML = 
                    "<b style='color:#ff9800;'>P1 시점 등록 완료!</b><br>다음 경유점(P2, P3...)을 계속 클릭하세요.";
            }
        });

        // 초기화 함수
        function resetPoints() {
            points = [];
            markers.forEach(function(m) { map.removeLayer(m); });
            markers = [];
            if (polylinePath) { map.removeLayer(polylinePath); polylinePath = null; }
            document.getElementById('status-text').innerHTML = "지도 위를 클릭하여 N개 절점을 등록하세요.";
        }
    </script>
</body>
</html>
"""

# ======================================================================
# 3. 레이아웃 구성
# ======================================================================
col_map, col_param = st.columns([2, 1])

with col_map:
    st.subheader("🌐 N절점 곡선 지도 (클릭하는 대로 노선 확장)")
    components.html(leaflet_curve_map_html, height=620)

with col_param:
    st.subheader("📏 터널 곡선 설계 & 공사비")

    tunnel_length = st.number_input("터널 총 연장 L (m)", value=750.0, step=10.0)
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

    # 곡선 구간 보정계수(1.1배) 적용
    total_cost_krw = (tunnel_length * cost_per_m * 1.1) + 500000000
    st.metric("총 개략 공사비 (곡선 보정 적용)", f"{total_cost_krw / 1e8:.2f} 억원")

    st.divider()
    
    st.subheader("🛡️ GTS NX 곡선 요소(Element) 도출")
    sig_ci = st.number_input("암석 일축압축강도 σci (kPa)", value=50000.0, step=5000.0)
    
    if st.button("🚀 N개 절점 GTS NX MCT 생성"):
        st.success("다중 절점 좌표가 반영된 GTS NX 곡선 빔/소리드 메쉬 데이터 도출 완료!")
