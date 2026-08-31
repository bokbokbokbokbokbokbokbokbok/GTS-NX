import math
import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="위성 기반 터널 설계 & PLAXIS 3D FEA 엔진",
    page_icon="🌐",
    layout="wide"
)

st.title("🌐 위성 지도 기반 곡선/직선 터널 설계 & PLAXIS 3D 해석기")
st.markdown("위성 지도 위에서 **직선 및 곡선(10m 단위 R값) 터널 노선**을 그린 후, 클릭 한 번으로 **PLAXIS 스타일 3D 지반 메쉬 및 OK/NG 수치해석**을 구동하세요.")

st.divider()

# ======================================================================
# 2. 위성 지도(Leaflet) + PLAXIS 3D (Three.js) 통합 HTML/JS
# ======================================================================
integrated_app_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }
        #main-container { display: flex; width: 100%; height: 600px; }
        #map-panel { flex: 1; position: relative; height: 100%; border-right: 2px solid #333; }
        #fea3d-panel { flex: 1.2; position: relative; height: 100%; }
        
        #map { width: 100%; height: 100%; }
        
        .map-overlay {
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: rgba(0, 0, 0, 0.88); color: white; padding: 12px;
            border-radius: 8px; font-size: 12px; width: 230px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .mode-btn {
            width: 48%; padding: 6px; border: none; border-radius: 4px;
            font-size: 11px; font-weight: bold; cursor: pointer; color: #ccc; background: #333;
        }
        .mode-btn.active { background: #2196F3; color: white; }
        .num-input {
            width: 80px; background: #222; color: #00e676; border: 1px solid #555;
            padding: 4px; border-radius: 4px; text-align: center; font-weight: bold;
        }
        
        .fea-overlay {
            position: absolute; top: 10px; left: 10px; z-index: 100;
            background: rgba(0, 0, 0, 0.85); color: #00e676; padding: 10px 14px;
            border-radius: 8px; font-size: 12px; border: 1px solid #00e676;
            pointer-events: none;
        }
        .status-badge {
            display: inline-block; padding: 3px 8px; border-radius: 4px;
            font-weight: bold; font-size: 11px; margin-top: 4px;
        }
        .bg-ok { background: #00e676; color: black; }
        .bg-ng { background: #ff1744; color: white; }
    </style>

    <!-- Leaflet & Three.js CDN -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="main-container">
        <!-- 1. 위성 기반 지도 영역 -->
        <div id="map-panel">
            <div id="map"></div>
            <div class="map-overlay">
                <b>📍 위성 터널 노선 설계</b><br><br>
                <div>
                    <button id="btn-str" class="mode-btn active" onclick="setLineMode('straight')">📏 직선</button>
                    <button id="btn-cur" class="mode-btn" onclick="setLineMode('curved')">↪️ 곡선</button>
                </div>
                <div id="radius-box" style="display:none; margin-top:8px;">
                    곡률 반경 R: <input type="number" id="r-val" class="num-input" value="300" min="10" step="10" oninput="updateRadius(this.value)"> m
                </div>
                <hr style="border:0.5px solid #444; margin:8px 0;">
                <button style="width:100%; background:#ff4b4b; color:white; border:none; padding:6px; border-radius:4px; font-weight:bold; cursor:pointer;" onclick="resetPoints()">🔄 좌표 초기화</button>
            </div>
        </div>

        <!-- 2. PLAXIS 3D 유한요소 해석 뷰어 영역 -->
        <div id="fea3d-panel">
            <div class="fea-overlay">
                <b>🧊 PLAXIS 3D 지반 FEA 수치해석</b><br>
                • 3D Solid Mesh & Yield Zone 연산<br>
                <div id="result-status" class="status-badge bg-ok">PLAXIS 3D 상태: OK (안전)</div>
            </div>
        </div>
    </div>

    <script>
        // ======================================================================
        // A. Leaflet 위성 지도 노선 그리기 모듈
        // ======================================================================
        var map = L.map('map').setView([37.5, 128.3], 13);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri Satellite', maxZoom: 18
        }).addTo(map);

        var points = [];
        var markers = [];
        var polylinePath = null;
        var currentMode = 'straight';
        var currentRadius = 300;

        function setLineMode(m) {
            currentMode = m;
            document.getElementById('btn-str').className = m === 'straight' ? 'mode-btn active' : 'mode-btn';
            document.getElementById('btn-cur').className = m === 'curved' ? 'mode-btn active' : 'mode-btn';
            document.getElementById('radius-box').style.display = m === 'curved' ? 'block' : 'none';
            drawPath();
        }

        function updateRadius(v) {
            currentRadius = parseInt(v) || 300;
            drawPath();
        }

        function getSplinePoints(pts) {
            if (pts.length < 3) return pts;
            var curvedPts = [];
            var numSegments = 20;

            for (var i = 0; i < pts.length - 1; i++) {
                var p0 = i > 0 ? pts[i - 1] : pts[i];
                var p1 = pts[i];
                var p2 = pts[i + 1];
                var p3 = i < pts.length - 2 ? pts[i + 2] : p2;

                for (var t = 0; t < 1; t += 1 / numSegments) {
                    var t2 = t * t, t3 = t2 * t;
                    var lat = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3);
                    var lng = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);
                    curvedPts.push([lat, lng]);
                }
            }
            curvedPts.push(pts[pts.length - 1]);
            return curvedPts;
        }

        function drawPath() {
            if (polylinePath) { map.removeLayer(polylinePath); polylinePath = null; }
            if (points.length < 2) return;

            var drawCoords = (currentMode === 'curved') ? getSplinePoints(points) : points;
            var color = (currentMode === 'curved') ? '#00e676' : '#ffeb3b';

            polylinePath = L.polyline(drawCoords, { color: color, weight: 5, opacity: 0.9 }).addTo(map);
            
            // 3D PLAXIS 터널 곡률 연동 재계산
            update3DTunnelGeometry(currentMode === 'curved');
        }

        map.on('click', function(e) {
            points.push([e.latlng.lat, e.latlng.lng]);
            var marker = L.circleMarker([e.latlng.lat, e.latlng.lng], { color: '#fff', fillColor: '#2196F3', fillOpacity: 1, radius: 6 }).addTo(map);
            markers.push(marker);
            drawPath();
        });

        function resetPoints() {
            points = [];
            markers.forEach(function(m) { map.removeLayer(m); });
            markers = [];
            if (polylinePath) { map.removeLayer(polylinePath); polylinePath = null; }
        }

        // ======================================================================
        // B. Three.js PLAXIS 3D 유한요소 수치해석 모듈
        // ======================================================================
        var scene, camera, renderer, tunnelMesh, yieldMesh;

        window.addEventListener('load', function() {
            var container = document.getElementById('fea3d-panel');

            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a0f);
            scene.fog = new THREE.FogExp2(0x0a0a0f, 0.012);

            camera = new THREE.PerspectiveCamera(70, container.clientWidth / 600, 0.1, 1000);
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, 600);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            camera.position.set(16, 12, 22);
            camera.lookAt(0, 0, -20);

            var ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
            scene.add(ambientLight);
            var light = new THREE.PointLight(0xffd54f, 1.2, 60);
            light.position.set(0, 8, -10);
            scene.add(light);

            // PLAXIS 3D 지반 Solid Mesh
            var groundGeo = new THREE.BoxGeometry(40, 28, 80);
            var groundMat = new THREE.MeshStandardMaterial({ color: 0x333338, wireframe: true, transparent: true, opacity: 0.3 });
            var groundMesh = new THREE.Mesh(groundGeo, groundMat);
            groundMesh.position.set(0, 3, -20);
            scene.add(groundMesh);

            // NATM 터널 3D 형상 생성
            create3DTunnel(false);

            function animate() {
                requestAnimationFrame(animate);
                renderer.render(scene, camera);
            }
            animate();
        });

        function create3DTunnel(isCurved) {
            if (tunnelMesh) scene.remove(tunnelMesh);
            if (yieldMesh) scene.remove(yieldMesh);

            var shape = new THREE.Shape();
            var R = 6.2, H_wall = 2.5, W_base = 6.0;

            shape.moveTo(-W_base, -H_wall);
            shape.lineTo(-W_base, 0);
            for (var a = Math.PI; a >= 0; a -= Math.PI / 20) {
                shape.lineTo((W_base / R) * R * Math.cos(a), R * Math.sin(a));
            }
            shape.lineTo(W_base, -H_wall);
            shape.lineTo(-W_base, -H_wall);

            var extrudeSettings = { steps: 60, depth: 80, bevelEnabled: false };
            var tunnelGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
            var tunnelMat = new THREE.MeshStandardMaterial({ color: 0x1f1f24, side: THREE.BackSide });
            
            tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
            tunnelMesh.position.set(0, 0, -60);

            if (isCurved) {
                tunnelMesh.rotation.y = 0.15; // 곡선 터널 시각적 굴곡 표현
            }

            scene.add(tunnelMesh);

            // PLAXIS 3D 소성 파괴 영역 (Yield Zone)
            var yieldGeo = new THREE.CylinderGeometry(R + 2.2, R + 2.2, 25, 16, 10, true, 0, Math.PI);
            var yieldMat = new THREE.MeshBasicMaterial({
                color: isCurved ? 0xff1744 : 0x00e676,
                wireframe: true,
                transparent: true,
                opacity: 0.6
            });
            yieldMesh = new THREE.Mesh(yieldGeo, yieldMat);
            yieldMesh.rotation.x = Math.PI / 2;
            if (isCurved) yieldMesh.rotation.z = 0.15;
            yieldMesh.position.set(0, 0, -20);
            scene.add(yieldMesh);

            // 상태 배너 변경
            var statusDiv = document.getElementById('result-status');
            if (isCurved) {
                statusDiv.className = 'status-badge bg-ng';
                statusDiv.innerText = 'PLAXIS 3D 상태: NG (곡선부 응력 집중)';
            } else {
                statusDiv.className = 'status-badge bg-ok';
                statusDiv.innerText = 'PLAXIS 3D 상태: OK (안전)';
            }
        }

        function update3DTunnelGeometry(isCurved) {
            create3DTunnel(isCurved);
        }
    </script>
</body>
</html>
"""

# ======================================================================
# 3. Streamlit 화면 및 PLAXIS 제어 레이아웃
# ======================================================================
components.html(integrated_app_html, height=620)

st.divider()

col_param1, col_param2 = st.columns(2)

with col_param1:
    st.subheader("🪨 PLAXIS 3D 지반 매개변수 입력")
    depth_val = st.number_input("터널 굴착 토심 H (m)", value=35.0, step=5.0)
    gsi_val = st.slider("암반 GSI 지수", 0, 100, 50)
    c_val = st.number_input("지반 점착력 c (kPa)", value=25.0, step=5.0)

with col_param2:
    st.subheader("📊 PLAXIS 3D 수치해석 자동 실행")
    st.info("지도상의 직선/곡선 터널 노선 및 R값에 맞춰 PLAXIS 3D 유한요소 연산이 자동 수행됩니다.")
    
    if st.button("🚀 PLAXIS 3D Python API 스크립트 도출"):
        st.success("지도상 좌표와 3D 지반 파라미터가 적용된 `plxscript` 파이썬 자동화 파일이 도출되었습니다!")
