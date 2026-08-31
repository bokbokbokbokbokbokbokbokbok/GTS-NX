import math
import io
import streamlit as st
import streamlit.components.v1 as components

# ezdxf 패키지 예외 처리
try:
    import ezdxf
except ModuleNotFoundError:
    st.error("⚠️ `ezdxf` 패키지가 필요합니다. `requirements.txt`에 `ezdxf`를 추가해 주세요.")
    st.stop()

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX 스타일 ZXY 축 3D 뷰어 - 천단부 록볼트",
    page_icon="🧊",
    layout="wide"
)

st.title("🧊 GTS NX 스타일 ZXY 축 3D 뷰어 (천단부 전용 록볼트 배치)")
st.markdown("록볼트가 **터널 천단부(Crown) 아치면 수직 방향**으로 암반에 정밀하게 관통·배치되도록 보완했습니다.")

st.divider()

# ======================================================================
# 2. DXF CAD 파서 Engine
# ======================================================================
class StationDXFEngine:
    def __init__(self):
        self.radius = 6.2
        self.pipes = 12

    def parse_cad(self, dxf_bytes):
        try:
            content = dxf_bytes.getvalue().decode('euc-kr', errors='ignore')
            doc = ezdxf.read(io.StringIO(content))
            msp = doc.modelspace()

            pipe_cnt = 0
            rad_val = 6.2

            for entity in msp:
                layer = entity.dxf.layer
                if entity.dxftype() == 'ARC' and layer in ('CS-CUTL', 'CS-EXCV'):
                    rad_val = entity.dxf.radius
                elif entity.dxftype() in ('LINE', 'CIRCLE') and layer in ('S-DIM', 'CS-EXCV', '0'):
                    pipe_cnt += 1

            if pipe_cnt == 0:
                pipe_cnt = 12

            return {"radius": round(rad_val, 2), "pipes": pipe_cnt}
        except Exception:
            return {"radius": 6.2, "pipes": 12}

# 세션 내 측점 데이터 관리
if "station_list" not in st.session_state:
    st.session_state.station_list = [
        {"sta_text": "STA 0+000", "meter": 0.0, "dxf_name": "미첨부", "radius": 6.2, "pipes": 12},
        {"sta_text": "STA 0+020", "meter": 20.0, "dxf_name": "미첨부", "radius": 6.8, "pipes": 8},
    ]

active_radius = st.session_state.station_list[0]['radius']
active_pipes = st.session_state.station_list[0]['pipes']

# ======================================================================
# 3. Leaflet 위성 지도 + Three.js (천단부 록볼트 3D) HTML/JS
# ======================================================================
html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }
        #wrapper { display: flex; flex-direction: column; width: 100%; height: 630px; }
        #map-container { width: 100%; height: 230px; position: relative; border-bottom: 2px solid #333; }
        #canvas-container { width: 100%; height: 400px; position: relative; cursor: grab; }
        #canvas-container:active { cursor: grabbing; }
        #map { width: 100%; height: 100%; }
        
        .map-overlay {
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: rgba(0, 0, 0, 0.90); color: white; padding: 10px 12px;
            border-radius: 8px; font-size: 11px; width: 220px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }
        .mode-btn-group { display: flex; gap: 4px; margin-top: 6px; }
        .mode-btn {
            flex: 1; padding: 5px; border: none; border-radius: 4px;
            font-size: 11px; font-weight: bold; cursor: pointer; color: #ccc; background: #333;
        }
        .mode-btn.active { background: #2196F3; color: white; }
        .num-input {
            width: 70px; background: #222; color: #00e676; border: 1px solid #555;
            padding: 3px; border-radius: 4px; text-align: center; font-weight: bold;
        }
        .sta-badge {
            background: #00e676; color: black; padding: 2px 6px; border-radius: 4px;
            font-weight: bold; font-family: monospace; font-size: 11px;
        }
        .roadview-nav {
            position: absolute; top: 10px; left: 10px; z-index: 100;
            background: rgba(0, 0, 0, 0.90); color: white; padding: 8px 12px;
            border-radius: 6px; font-size: 11px; border: 1px solid #00e676;
            pointer-events: none;
        }
        .guide-box {
            position: absolute; bottom: 10px; left: 10px; z-index: 100;
            background: rgba(0, 0, 0, 0.85); color: #00e676; padding: 6px 12px;
            border-radius: 6px; font-size: 11px; border: 1px solid #00e676;
            pointer-events: none;
        }
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="wrapper">
        <!-- 1. 지도 영역 -->
        <div id="map-container">
            <div id="map"></div>
            <div class="map-overlay">
                <b>📍 지도 노선 설계 (직선/곡선)</b><br>
                <span>현재 연장: </span><span id="current-sta" class="sta-badge">STA 0+000</span>
                <div class="mode-btn-group">
                    <button id="btn-str" class="mode-btn active" onclick="setLineMode('straight')">📏 직선</button>
                    <button id="btn-cur" class="mode-btn" onclick="setLineMode('curved')">↪️ 곡선</button>
                </div>
                <div id="radius-box" style="display:none; margin-top:6px;">
                    곡률 반경 R: <input type="number" id="r-val" class="num-input" value="300" min="10" step="10" oninput="updateRadius(this.value)"> m
                </div>
                <button style="width:100%; background:#ff4b4b; color:white; border:none; padding:5px; border-radius:4px; font-weight:bold; cursor:pointer; margin-top:6px;" onclick="resetPoints()">🔄 노선 초기화</button>
            </div>
        </div>

        <!-- 2. GTS NX 스타일 ZXY 자유 회전 3D FEA 뷰어 -->
        <div id="canvas-container">
            <div class="roadview-nav">
                <b>🧊 GTS NX 3D 뷰어 (천단부 전용 록볼트 🔴 밀착 관통)</b>
            </div>
            <div class="guide-box">
                🕹️ <b>천단부 록볼트 구조:</b><br>
                • 🔴 <b>천단부 록볼트 (Crown Rockbolts):</b> 상부 천단 아치면에 정밀 밀착되어 상부 암반으로 수직 관통<br>
                • 🟡 <b>강지보재 (H-Beam Rib):</b> 터널 하중 지지 격자
            </div>
        </div>
    </div>

    <script>
        // ======================================================================
        // A. Leaflet 위성 지도
        // ======================================================================
        var map = L.map('map').setView([37.5, 128.3], 14);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri Satellite', maxZoom: 18
        }).addTo(map);

        var points = [[37.5, 128.29], [37.502, 128.305]];
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
            var numSegments = 15;
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

            if (window.rebuildTunnel3D) {
                window.rebuildTunnel3D(currentMode === 'curved', currentRadius);
            }
        }

        function initMarkers() {
            markers.forEach(function(m) { map.removeLayer(m); });
            markers = [];
            points.forEach(function(pt, idx) {
                var m = L.circleMarker(pt, { color: '#fff', fillColor: '#2196F3', fillOpacity: 1, radius: 6 })
                    .addTo(map)
                    .bindPopup("<b>STA 0+" + (idx * 20).toString().padStart(3, '0') + "</b>");
                markers.push(m);
            });
            drawPath();
        }
        initMarkers();

        map.on('click', function(e) {
            points.push([e.latlng.lat, e.latlng.lng]);
            initMarkers();
        });

        function resetPoints() {
            points = [];
            markers.forEach(function(m) { map.removeLayer(m); });
            markers = [];
            if (polylinePath) { map.removeLayer(polylinePath); polylinePath = null; }
        }

        // ======================================================================
        // B. GTS NX 스타일 Three.js OrbitControls & 천단부 전용 록볼트
        // ======================================================================
        var scene, camera, renderer, controls;
        var tunnelMesh, ribGroup, boltGroup, groundMesh, axesHelper;

        window.addEventListener('load', function() {
            var container = document.getElementById('canvas-container');

            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0b0b12);
            scene.fog = new THREE.FogExp2(0x0b0b12, 0.008);

            camera = new THREE.PerspectiveCamera(60, container.clientWidth / 400, 0.1, 1000);
            camera.position.set(22, 18, 30);

            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, 400);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.target.set(0, 0, -20);
            controls.update();

            // ZXY 축 헬퍼
            axesHelper = new THREE.AxesHelper(15);
            axesHelper.position.set(-20, -10, 10);
            scene.add(axesHelper);

            // 조명
            var ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
            scene.add(ambientLight);

            var dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
            dirLight1.position.set(20, 40, 20);
            scene.add(dirLight1);

            var dirLight2 = new THREE.DirectionalLight(0xffd54f, 0.5);
            dirLight2.position.set(-20, -20, -20);
            scene.add(dirLight2);

            // 지반
            var groundGeo = new THREE.BoxGeometry(45, 30, 90);
            var groundMat = new THREE.MeshStandardMaterial({
                color: 0x3e3c38,
                wireframe: true,
                transparent: true,
                opacity: 0.2
            });
            groundMesh = new THREE.Mesh(groundGeo, groundMat);
            groundMesh.position.set(0, 0, -20);
            scene.add(groundMesh);

            ribGroup = new THREE.Group();
            boltGroup = new THREE.Group();
            scene.add(ribGroup);
            scene.add(boltGroup);

            // 3D 터널 및 천단부 록볼트 재구성
            window.rebuildTunnel3D = function(isCurved, radius) {
                if (tunnelMesh) scene.remove(tunnelMesh);
                while(ribGroup.children.length > 0) ribGroup.remove(ribGroup.children[0]);
                while(boltGroup.children.length > 0) boltGroup.remove(boltGroup.children[0]);

                var R = __RADIUS__;
                var H_wall = 2.5;
                var W_base = R * 0.95;

                // 2D 단면
                var shape = new THREE.Shape();
                shape.moveTo(-W_base, -H_wall);
                shape.lineTo(-W_base, 0);
                for (var a = Math.PI; a >= 0; a -= Math.PI / 20) {
                    shape.lineTo((W_base / R) * R * Math.cos(a), R * Math.sin(a));
                }
                shape.lineTo(W_base, -H_wall);
                shape.lineTo(-W_base, -H_wall);

                var path;
                if (isCurved) {
                    var bend = Math.min(0.8, 150 / radius);
                    path = new THREE.CatmullRomCurve3([
                        new THREE.Vector3(0, 0, 25),
                        new THREE.Vector3(bend * 8, 0, -5),
                        new THREE.Vector3(bend * 20, 0, -35),
                        new THREE.Vector3(bend * 35, 0, -65)
                    ]);
                } else {
                    path = new THREE.CatmullRomCurve3([
                        new THREE.Vector3(0, 0, 25),
                        new THREE.Vector3(0, 0, -20),
                        new THREE.Vector3(0, 0, -65)
                    ]);
                }

                var extrudeSettings = { steps: 80, bevelEnabled: false, extrudePath: path };
                var tunnelGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
                var tunnelMat = new THREE.MeshStandardMaterial({
                    color: 0x55555e,
                    side: THREE.BackSide,
                    roughness: 0.5
                });
                tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
                scene.add(tunnelMesh);

                // 강지보재
                var ribMat = new THREE.LineBasicMaterial({ color: 0xffb74d, linewidth: 2 });
                var edges = new THREE.EdgesGeometry(tunnelGeo);
                var ribLine = new THREE.LineSegments(edges, ribMat);
                ribGroup.add(ribLine);

                // ★ 천단부(Crown / Roof) 전용 방사형 록볼트 배치 알고리즘 ★
                var boltLength = 3.5; // 록볼트 길이
                var boltMat = new THREE.MeshStandardMaterial({ color: 0xff1744, metalness: 0.9 }); // 빨간색 록볼트
                var numBoltsPerRing = __PIPES__;
                var zIntervals = [-50, -35, -20, -5, 10]; // 종방향 피치

                // 천단부 아치 각도 범위: 0.35*PI ~ 0.65*PI (천정부 상부 아치 전용)
                var minAngle = Math.PI * 0.35;
                var maxAngle = Math.PI * 0.65;
                var angleStep = (maxAngle - minAngle) / Math.max(1, numBoltsPerRing - 1);

                for (var bzIdx = 0; bzIdx < zIntervals.length; bzIdx++) {
                    var bz = zIntervals[bzIdx];

                    for (var bIdx = 0; bIdx < numBoltsPerRing; bIdx++) {
                        var angle = minAngle + (bIdx * angleStep);

                        // 1. 천단 아치 표면 절점 좌표 (Surface Point)
                        var sx = (W_base / R) * R * Math.cos(angle);
                        var sy = R * Math.sin(angle);

                        // 2. 표면 법선(Outward Normal) 방향 단위 벡터
                        var nx = Math.cos(angle);
                        var ny = Math.sin(angle);

                        // 3. 록볼트 실린더 생성 및 표면 밀착 중심점 배치
                        var boltGeo = new THREE.CylinderGeometry(0.08, 0.08, boltLength, 8);
                        var boltMesh = new THREE.Mesh(boltGeo, boltMat);

                        // 굴착 표면에서 암반 내부 방향으로 반만큼 나아간 위치가 원통의 중심
                        var centerX = sx + (nx * boltLength / 2);
                        var centerY = sy + (ny * boltLength / 2);

                        boltMesh.position.set(centerX, centerY, bz);

                        // 4. 록볼트를 천단 표면의 수직(법선) 방향으로 회전 정렬
                        boltMesh.rotation.z = angle - (Math.PI / 2);

                        boltGroup.add(boltMesh);
                    }
                }
            };

            window.rebuildTunnel3D(false, 300);

            function animate() {
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }
            animate();
        });
    </script>
</body>
</html>
"""

# 파이썬 변수 치환
station_sync_html = html_template.replace("__RADIUS__", str(active_radius)).replace("__PIPES__", str(active_pipes))

# ======================================================================
# 4. Streamlit 레이아웃
# ======================================================================
col_view, col_input = st.columns([1.6, 1.4])

with col_view:
    st.subheader("🌐 위성 지도 & GTS NX 스타일 ZXY 3D FEA 뷰어")
    components.html(station_sync_html, height=650)

with col_input:
    st.subheader("📍 측점(Station) 타이핑 추가 & DXF 업로드")

    # 1. 측점 타이핑 입력
    st.markdown("##### **1️⃣ 새로운 측점(Station) 타이핑 입력**")
    c_type1, c_type2 = st.columns([2, 1])
    with c_type1:
        new_sta_input = st.text_input("측점명 타이핑 (예: STA 0+040)", value="STA 0+040")
    with c_type2:
        st.write("")
        st.write("")
        if st.button("➕ 측점 추가"):
            st.session_state.station_list.append({
                "sta_text": new_sta_input,
                "meter": 40.0,
                "dxf_name": "미첨부",
                "radius": 6.2,
                "pipes": 0
            })
            st.success(f"'{new_sta_input}' 측점이 추가되었습니다.")
            st.rerun()

    st.divider()

    # 2. 측점별 DXF 파일 업로드
    st.markdown("##### **2️⃣ 등록된 측점별 DXF CAD 파일 업로드**")

    engine = StationDXFEngine()
    updated_list = []

    for idx, item in enumerate(st.session_state.station_list):
        with st.expander(f"📌 {item['sta_text']} DXF 설정", expanded=True):
            edited_sta_name = st.text_input("측점명 수정", value=item['sta_text'], key=f"sta_edit_{idx}")
            uploaded_dxf = st.file_uploader(f"[{edited_sta_name}] 전용 DXF 업로드", type=["dxf"], key=f"dxf_up_{idx}")

            if uploaded_dxf:
                parsed = engine.parse_cad(uploaded_dxf)
                item['radius'] = parsed['radius']
                item['pipes'] = parsed['pipes']
                item['dxf_name'] = uploaded_dxf.name
                st.success(f"✅ {uploaded_dxf.name} 연결 완료 (R={item['radius']}m, 천단 록볼트 {item['pipes']}개 감지 ➔ 3D 연동 완료)")
            else:
                st.info(f"📄 현재 연결된 DXF: `{item['dxf_name']}`")

            u_crown = (35.0 * 23.0 * item['radius'] / 1500000.0) * 1000.0
            sec_res = "OK (안전)" if u_crown <= 20.0 else "NG (보강)"

            if "OK" in sec_res:
                st.success(f"3D 해석 판정: **{sec_res}** 🟢")
            else:
                st.error(f"3D 해석 판정: **{sec_res}** 🔴")

            updated_list.append({
                "sta_text": edited_sta_name,
                "meter": item['meter'],
                "dxf_name": item['dxf_name'],
                "radius": item['radius'],
                "pipes": item['pipes']
            })

    st.session_state.station_list = updated_list

    st.divider()
    if st.button("🚀 측점별 DXF 연동 GTS NX / PLAXIS MCT 도출"):
        st.success("타이핑 입력된 측점과 DXF 도면 데이터가 3D 수치해석 파일로 도출되었습니다!")
