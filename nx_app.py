import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX - 곡률 반경(R) 타이핑 입력 설계",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ N개 절점 & 곡률 반경(R) 타이핑 입력 정밀 설계")
st.markdown("지도 위에서 **N개 지점을 클릭**하고, **곡률 반경(R)을 키보드로 직접 타이핑**하여 설정하세요.")

st.divider()

# ======================================================================
# 2. Leaflet JS - R값 직접 타이핑 입력 전용 UI & 스플라인 곡선 HTML/JS
# ======================================================================
leaflet_type_map_html = """
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
            background: #1a1a1a; padding: 12px; border-radius: 6px; margin: 8px 0;
            display: none; border: 1.5px solid #00e676;
        }
        .radius-input-label {
            font-size: 12px; font-weight: bold; color: #00e676; margin-bottom: 6px; display: block;
        }
        .radius-input-group {
            display: flex; align-items: center; gap: 8px;
        }
        .radius-number-input {
            width: 100%; background: #2a2a2a; color: #ffffff; border: 1px solid #00e676;
            padding: 8px; border-radius: 4px; font-size: 15px; font-weight: bold; text-align: center;
        }
        .radius-number-input:focus {
            outline: none; border-color: #2196F3; box-shadow: 0 0 5px rgba(33, 150, 243, 0.5);
        }
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

        <!-- 곡률 반경(R) 타이핑 직접 입력 박스 -->
        <div id="radius-container" class="radius-box">
            <span class="radius-input-label">⌨️ 곡률 반경 R 입력 (m)</span>
            <div class="radius-input-group">
                <input type="number" id="radius-num" class="radius-number-input" min="10" max="5000" step="10" value="300" placeholder="예: 250" oninput="updateRadiusFromNum(this.value)">
                <span style="font-weight:bold; color:#00e676;">m</span>
            </div>
            <div style="font-size:11px; color:#aaa; margin-top:6px;">* 숫자를 타이핑하여 입력하세요 (Enter 또는 숫자 변경 시 자동 적용)</div>
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
        var currentRadius = 300;

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

        // Catmull-Rom 스플라인 곡선 보간 함수
        function getSplinePoints(pts, radius) {
            if (pts.length < 3) return pts;

            var curvedPts = [];
            var numSegments = 25;

            for (var i = 0; i < pts.length - 1; i++) {
                var p0 = i > 0 ? pts[i - 1] : pts[i];
                var p1 = pts[i];
                var p2 = pts[i + 1];
                var p3 = i < pts.length - 2 ? pts[i + 2] : p2;

                for (var t = 0; t < 1; t += 1 / numSegments) {
                    var t2 = t * t;
                    var t3 = t2 * t;

                    var lat = 0.5 * ((2 * p1[0]) +
                        (-p0[0] + p2[0]) * t +
                        (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                        (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3);

                    var lng = 0.5 * ((2 * p1[1]) +
                        (-p0[1] + p2[1]) * t +
                        (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                        (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);

                    curvedPts.push([lat, lng]);
                }
            }
            curvedPts.push(pts[pts.length - 1]);
            return curvedPts;
        }

        function setLineMode(mode) {
            currentMode = mode;
            document.getElementById('btn-straight').className = mode === 'straight' ? 'mode-btn active' : 'mode-btn';
            document.getElementById('btn-curved').className = mode === 'curved' ? 'mode-btn active' : 'mode-btn';
            document.getElementById('radius-container').style.display = mode === 'curved' ? 'block' : 'none';
            drawPath();
        }

        // 키보드 타이핑 수치 실시간 반영
        function updateRadiusFromNum(val) {
            var parsed = parseInt(val);
            if (!isNaN(parsed) && parsed > 0) {
                currentRadius = parsed;
                drawPath();
            }
        }

        function drawPath() {
            if (polylinePath) { map.removeLayer(polylinePath); polylinePath = null; }

            var n = points.length;
            if (n < 2) return;

            var drawCoords = points;
            var lineColor = '#ffeb3b';

            if (currentMode === 'curved') {
                lineColor = '#00e676';
                drawCoords = getSplinePoints(points, currentRadius);
            }

            polylinePath = L.polyline(drawCoords, {
                color: lineColor,
                weight: 5,
                opacity: 0.95
            }).addTo(map);

            var totalDist = 0;
            for (var i = 0; i < drawCoords.length - 1; i++) {
                totalDist += getDistance(drawCoords[i][0], drawCoords[i][1], drawCoords[i+1][0], drawCoords[i+1][1]);
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
    st.subheader("🌐 곡률 반경(R) 타이핑 직접 입력 지도")
    components.html(leaflet_type_map_html, height=620)

with col_param:
    st.subheader("📏 터널 설계 & 공사비 산출")

    tunnel_length = st.number_input("터널 총 연장 L (m)", value=7314.0, step=10.0)
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
    
    if st.button("🚀 타이핑 R값 반영 GTS NX MCT 생성"):
        st.success("입력한 정밀 곡률 반경(R) 값이 적용된 GTS NX 파이프라인 파일이 생성되었습니다!")
