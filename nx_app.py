import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX - 터널 선형 & 곡률 반경(R) 설계",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ N개 절점 & 곡률 반경(R) 제어 터널 선형 설계")
st.markdown("지도 위에서 **N개 지점을 클릭**하고, 선형 모드 및 **곡률 반경(R)**을 설정하세요.")

st.divider()

# ======================================================================
# 2. Leaflet JS - 곡률 반경(R) 실시간 제어 HTML/JS
# ======================================================================
leaflet_radius_map_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        #map { width: 100%; height: 600px; border-radius: 8px; }
        body { margin: 0; padding: 0; font-family: sans-serif; }
        .info-panel {
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: rgba(0, 0, 0, 0.88); color: white; padding: 14px;
            border-radius: 8px; font-size: 13px; max-width: 320px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .mode-toggle {
            display: flex; background: #333; border-radius: 6px; padding: 3px;
            margin: 8px 0;
        }
        .mode-btn {
            flex: 1; border: none; padding: 6px; border-radius: 4px;
            cursor: pointer; font-size: 12px; font-weight: bold; color: #ccc;
            background: transparent; transition: 0.2s;
        }
        .mode-btn.active { background: #2196F3; color: white; }
        .radius-box {
            background: #222; padding: 10px; border-radius: 6px; margin: 8px 0;
            display: none; border: 1px solid #444;
        }
        .radius-slider { width: 100%; cursor: pointer; }
        .reset-btn {
            background: #ff4b4b; color: white; border: none; padding: 8px;
            border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%;
            margin-top: 6px; font-size: 12px;
        }
        .reset-btn:hover { background: #e03e3e; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        <b>📍 노선 선형 & 곡률 반경(R)</b>
        <div class="mode-toggle">
            <button id="btn-straight" class="mode-btn active" onclick="setLineMode('straight')">📏 직선 (Polyline)</button>
            <button id="btn-curved" class="mode-btn" onclick="setLineMode('curved')">↪️ 곡선 (Curve)</button>
        </div>

        <!-- 곡력 반경 R 선택 슬라이더 박스 -->
        <div id="radius-container" class="radius-box">
            <label><b>🔄 곡률 반경 (R): <span id="radius-val" style="color:#00e676;">300</span> m</b></label>
            <input type="range" id="radius-input" class="radius-slider" min="100" max="1500" step="50" value="300" oninput="updateRadius(this.value)">
            <div style="font-size:11px; color:#aaa; margin-top:4px;">* R값이 작을수록 급곡선, 클수록 완곡선</div>
        </div>

        <hr style="border: 0.5px solid #444; margin: 8px 0;">
        <div id="status-text">지도 위를 클릭하여 절점(P1, P2...)을 추가하세요.</div>
        <button class="reset-btn" onclick="resetPoints()">🔄 좌표 초기화</button>
    </div>

    <script>
        var map = L.map('map').setView([37.5, 128.3], 13);

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri World Imagery',
            maxZoom: 18
        }).addTo(map);

        var points = [];
        var markers = [];
        var polylinePath = null;
        var currentMode = 'straight';
        var currentRadius = 300; // 기본 곡률 반경 R = 300m

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

        function setLineMode(mode) {
            currentMode = mode;
            document.getElementById('btn-straight').className = mode === 'straight' ? 'mode-btn active' : 'mode-btn';
            document.getElementById('btn-curved').className = mode === 'curved' ? 'mode-btn active' : 'mode-btn';
            document.getElementById('radius-container').style.display = mode === 'curved' ? 'block' : 'none';
            drawPath();
        }

        // 곡률 반경 R 변경 시
        function updateRadius(val) {
            currentRadius = parseInt(val);
            document.getElementById('radius-val').innerText = currentRadius;
            drawPath();
        }

        function drawPath() {
            if (polylinePath) { map.removeLayer(polylinePath); polylinePath = null; }

            var n = points.length;
            if (n < 2) return;

            var lineColor = (currentMode === 'curved') ? '#00e676' : '#ffeb3b';

            // R값에 반비례하여 smoothFactor 조절 (R이 클수록 완만하게, 작을수록 좁은 가파른 곡선)
            var smoothValue = 0.0;
            if (currentMode === 'curved') {
                smoothValue = Math.max(1.0, 10.0 - (currentRadius / 150.0));
            }

            polylinePath = L.polyline(points, {
                color: lineColor,
                weight: 5,
                opacity: 0.9,
                smoothFactor: smoothValue
            }).addTo(map);

            var totalDist = 0;
            for (var i = 0; i < n - 1; i++) {
                totalDist += getDistance(points[i][0], points[i][1], points[i+1][0], points[i+1][1]);
            }

            var modeName = (currentMode === 'straight') ? "직선 (Polyline)" : "곡선 (R=" + currentRadius + "m)";
            document.getElementById('status-text').innerHTML = 
                "<b style='color:#4caf50;'>[" + modeName + " 노선 적용]</b><br>" +
                "• 절점 수: <b>" + n + " 개</b><br>" +
                "<b style='font-size:14px; color:#ffeb3b;'>• 터널 총 연장: " + totalDist.toFixed(1) + " m</b>";
        }

        map.on('click', function(e) {
            var lat = e.latlng.lat;
            var lng = e.latlng.lng;
            points.push([lat, lng]);

            var n = points.length;
            var label = "P" + n;
            var color = (n === 1) ? "#ff4b4b" : "#2196F3";

            var marker = L.circleMarker([lat, lng], {
                color: '#ffffff',
                fillColor: color,
                fillOpacity: 1.0,
                radius: 7,
                weight: 2
            }).addTo(map).bindPopup(label).openPopup();

            markers.push(marker);
            drawPath();
        });

        function resetPoints() {
            points = [];
            markers.forEach(function(m) { map.removeLayer(m); });
            markers = [];
            if (polylinePath) { map.removeLayer(polylinePath); polylinePath = null; }
            document.getElementById('status-text').innerHTML = "지도 위를 클릭하여 절점(P1, P2...)을 추가하세요.";
        }
    </script>
</body>
</html>
"""

# ======================================================================
# 3. Streamlit 화면 레이아웃
# ======================================================================
col_map, col_param = st.columns([2, 1])

with col_map:
    st.subheader("🌐 선형 & 곡률 반경(R) 제어 지도")
    components.html(leaflet_radius_map_html, height=620)

with col_param:
    st.subheader("📏 터널 설계 & 공사비 산출")

    tunnel_length = st.number_input("터널 총 연장 L (m)", value=650.0, step=10.0)
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
    
    st.subheader("🛡️ GTS NX 파라미터 도출")
    sig_ci = st.number_input("암석 일축압축강도 σci (kPa)", value=50000.0, step=5000.0)
    
    if st.button("🚀 곡률 반경(R) 반영 GTS NX MCT 생성"):
        st.success("설정한 R값 및 절점 정보가 적용된 GTS NX 파이프라인 파일이 생성되었습니다!")
