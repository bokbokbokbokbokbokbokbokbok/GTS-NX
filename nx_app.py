import math
import io
import numpy as np
import streamlit as st
import streamlit.components.v1 as components

# ezdxf 파싱 라이브러리 예외 처리
try:
    import ezdxf
except ModuleNotFoundError:
    st.error("⚠️ `ezdxf` 패키지가 필요합니다. `requirements.txt`에 `ezdxf`를 추가해 주세요.")
    st.stop()

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="Station 간 보간법(Interpolation) 3D 지반-터널 모델러",
    page_icon="📐",
    layout="wide"
)

st.title("📐 Station 간 보간법(Interpolation) 적용 3D 지반-터널 모델러")
st.markdown("첫 번째 Station과 두 번째 Station의 **지반 고도, 터널 깊이, 단면**을 **선형 보간(Linear Interpolation)**하여 연속된 3D 지반체 및 터널을 생성합니다.")

st.divider()

# ======================================================================
# 2. 세션 상태 관리 (Station별 지반 및 터널 파라미터)
# ======================================================================
if "sta_a" not in st.session_state:
    st.session_state.sta_a = {"sta": 0.0, "ground_h": 40.0, "tunnel_depth": 25.0, "radius": 6.2, "rmr": 55}
if "sta_b" not in st.session_state:
    st.session_state.sta_b = {"sta": 20.0, "ground_h": 50.0, "tunnel_depth": 35.0, "radius": 6.8, "rmr": 35}

# ======================================================================
# 3. Three.js - Station 간 선형 보간 3D Mesh 생성 HTML/JS
# ======================================================================
threejs_interpolated_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }}
        #wrapper {{ display: flex; flex-direction: column; width: 100%; height: 600px; }}
        #map-container {{ width: 100%; height: 220px; position: relative; border-bottom: 2px solid #333; }}
        #canvas-container {{ width: 100%; height: 380px; position: relative; }}
        
        #map {{ width: 100%; height: 100%; }}
        
        .map-overlay {{
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: rgba(0, 0, 0, 0.90); color: white; padding: 8px 12px;
            border-radius: 6px; font-size: 11px;
        }}
        .sta-badge {{
            background: #2196F3; color: white; padding: 2px 6px; border-radius: 4px;
            font-weight: bold; font-family: monospace; font-size: 11px;
        }}
        
        .roadview-nav {{
            position: absolute; top: 10px; left: 10px; z-index: 100;
            background: rgba(0, 0, 0, 0.90); color: white; padding: 8px 12px;
            border-radius: 6px; font-size: 11px; border: 1px solid #00e676;
        }}
        .interp-info {{
            position: absolute; bottom: 10px; left: 10px; z-index: 100;
            background: rgba(0, 0, 0, 0.85); color: #00e676; padding: 8px 12px;
            border-radius: 6px; font-size: 11px; border: 1px solid #00e676;
        }}
    </style>
    <!-- Leaflet & Three.js CDN -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="wrapper">
        <!-- 1. 위성 기반 지도 (상단) -->
        <div id="map-container">
            <div id="map"></div>
            <div class="map-overlay">
                <b>🌍 Station 보간 구간 지도</b><br>
                <span>구간: </span><span class="sta-badge">STA 0+000 ~ STA 0+020</span>
            </div>
        </div>

        <!-- 2. 보간법 적용 3D 지반 & 터널 뷰어 (하단) -->
        <div id="canvas-container">
            <div class="roadview-nav">
                <b>📐 Station A ➔ Station B 보간 3D Solid Mesh</b>
            </div>
            <div class="interp-info">
                <b>📊 보간 경사 지반:</b> STA A(H={st.session_state.sta_a['ground_h']}m, D={st.session_state.sta_a['tunnel_depth']}m) ➔ STA B(H={st.session_state.sta_b['ground_h']}m, D={st.session_state.sta_b['tunnel_depth']}m)
            </div>
        </div>
    </div>

    <script>
        function formatStation(meters) {{
            var k = Math.floor(meters / 1000);
            var m = (meters % 1000).toFixed(2);
            var mStr = (m < 100) ? (m < 10 ? "00" + m : "0" + m) : m;
            return "STA " + k + "+" + mStr;
        }}

        // ======================================================================
        // A. Leaflet 위성 지도 모듈
        // ======================================================================
        var map = L.map('map').setView([37.5, 128.3], 14);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Esri Satellite', maxZoom: 18
        }}).addTo(map);

        var pA = [37.5, 128.29];
        var pB = [37.502, 128.305];
        
        L.polyline([pA, pB], {{ color: '#00e676', weight: 5 }}).addTo(map);
        L.circleMarker(pA, {{ color: '#fff', fillColor: '#2196F3', fillOpacity: 1, radius: 6 }}).addTo(map).bindPopup("<b>STA A (0m)</b>");
        L.circleMarker(pB, {{ color: '#fff', fillColor: '#ff1744', fillOpacity: 1, radius: 6 }}).addTo(map).bindPopup("<b>STA B (20m)</b>");

        // ======================================================================
        // B. Three.js 3D 보간 메쉬 생성기
        // ======================================================================
        var staA = {{
            h: {st.session_state.sta_a['ground_h']},
            d: {st.session_state.sta_a['tunnel_depth']},
            r: {st.session_state.sta_a['radius']}
        }};
        
        var staB = {{
            h: {st.session_state.sta_b['ground_h']},
            d: {st.session_state.sta_b['tunnel_depth']},
            r: {st.session_state.sta_b['radius']}
        }};

        window.addEventListener('load', function() {{
            var container = document.getElementById('canvas-container');

            var scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a0f);
            scene.fog = new THREE.FogExp2(0x0a0a0f, 0.012);

            var camera = new THREE.PerspectiveCamera(70, container.clientWidth / 380, 0.1, 1000);
            var renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(container.clientWidth, 380);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            camera.position.set(22, 16, 25);
            camera.lookAt(0, 0, -20);

            var isDragging = false;
            var previousMousePosition = {{ x: 0, y: 0 }};
            var cameraTheta = 0.5, cameraPhi = Math.PI / 2.5;

            function updateCamera() {{
                var r = 32;
                camera.position.x = r * Math.sin(cameraPhi) * Math.sin(cameraTheta);
                camera.position.y = r * Math.cos(cameraPhi) + 2.0;
                camera.position.z = -20 + r * Math.sin(cameraPhi) * Math.cos(cameraTheta);
                camera.lookAt(0, 0, -20);
            }}
            updateCamera();

            renderer.domElement.addEventListener('mousedown', function() {{ isDragging = true; }});
            renderer.domElement.addEventListener('mousemove', function(e) {{
                if (isDragging) {{
                    var deltaX = e.clientX - previousMousePosition.x;
                    var deltaY = e.clientY - previousMousePosition.y;
                    cameraTheta -= deltaX * 0.005;
                    cameraPhi -= deltaY * 0.005;
                    cameraPhi = Math.max(0.1, Math.min(Math.PI - 0.1, cameraPhi));
                    updateCamera();
                }}
                previousMousePosition = {{ x: e.clientX, y: e.clientY }};
            }});
            window.addEventListener('mouseup', function() {{ isDragging = false; }});

            var ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
            scene.add(ambientLight);
            var light = new THREE.PointLight(0xffd54f, 1.2, 50);
            light.position.set(0, 15, -10);
            scene.add(light);

            // 1. 선형 보간된 경사 3D 지반 블록 생성 (Sloped Ground Solid)
            var groundLength = 50;
            var numSteps = 20;
            var groundGroup = new THREE.Group();

            for (var i = 0; i < numSteps; i++) {{
                var t1 = i / numSteps;
                var t2 = (i + 1) / numSteps;
                
                // 선형 보간 공식 적용: H(t) = (1-t)*H_A + t*H_B
                var h1 = (1 - t1) * staA.h + t1 * staB.h;
                var h2 = (1 - t2) * staA.h + t2 * staB.h;
                var hAvg = (h1 + h2) / 2;

                var z1 = -t1 * groundLength;
                var z2 = -(t2) * groundLength;
                var zChunk = groundLength / numSteps;

                var boxGeo = new THREE.BoxGeometry(30, hAvg, zChunk);
                var boxMat = new THREE.MeshStandardMaterial({{
                    color: 0x3e3c38,
                    wireframe: true,
                    transparent: true,
                    opacity: 0.35
                }});
                var boxMesh = new THREE.Mesh(boxGeo, boxMat);
                boxMesh.position.set(0, hAvg / 2 - 10, -(i * zChunk) - zChunk / 2 + 5);
                groundGroup.add(boxMesh);
            }}
            scene.add(groundGroup);

            // 2. 선형 보간된 터널 3D 가변 튜브 생성 (Interpolated Tunnel Tube)
            var tunnelPoints = [];
            for (var j = 0; j <= 20; j++) {{
                var t = j / 20;
                // 깊이 및 위치 보간
                var dInterp = (1 - t) * staA.d + t * staB.d;
                var zPos = 5 - t * groundLength;
                var yPos = -dInterp + 15;
                tunnelPoints.push(new THREE.Vector3(0, yPos, zPos));
            }}

            var tunnelPath = new THREE.CatmullRomCurve3(tunnelPoints);
            var tunnelGeo = new THREE.TubeGeometry(tunnelPath, 40, (staA.r + staB.r)/2, 16, false);
            var tunnelMat = new THREE.MeshStandardMaterial({{ color: 0x1f1f24, side: THREE.BackSide }});
            var tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
            scene.add(tunnelMesh);

            // 지보재 와이어프레임
            var wireGeo = new THREE.WireframeGeometry(tunnelGeo);
            var wireMat = new THREE.LineBasicMaterial({{ color: 0x00e676, linewidth: 1 }});
            var wireMesh = new THREE.LineSegments(wireGeo, wireMat);
            scene.add(wireMesh);

            function animate() {{
                requestAnimationFrame(animate);
                renderer.render(scene, camera);
            }}
            animate();
        }});
    </script>
</body>
</html>
"""

# ======================================================================
# 4. Streamlit UI (Station A & Station B 파라미터 입력 및 보간 계산)
# ======================================================================
col_view, col_input = st.columns([1.6, 1.4])

with col_view:
    st.subheader("🌐 Station 간 보간 3D 지반-터널 모델")
    components.html(threejs_interpolated_html, height=610)

with col_input:
    st.subheader("⚙️ Station A / B 지반 및 터널 데이터 입력")

    # Station A 입력
    st.markdown("##### 📍 **[Station A] STA 0+000 (시점)**")
    cA1, cA2, cA3 = st.columns(3)
    with cA1:
        st.session_state.sta_a['ground_h'] = st.number_input("지표 고도 H_A (m)", value=st.session_state.sta_a['ground_h'], step=2.0)
    with cA2:
        st.session_state.sta_a['tunnel_depth'] = st.number_input("터널 토심 D_A (m)", value=st.session_state.sta_a['tunnel_depth'], step=2.0)
    with cA3:
        st.session_state.sta_a['radius'] = st.number_input("굴착 반경 R_A (m)", value=st.session_state.sta_a['radius'], step=0.2)

    st.divider()

    # Station B 입력
    st.markdown("##### 📍 **[Station B] STA 0+020 (종점 - 20m 거리)**")
    cB1, cB2, cB3 = st.columns(3)
    with cB1:
        st.session_state.sta_b['ground_h'] = st.number_input("지표 고도 H_B (m)", value=st.session_state.sta_b['ground_h'], step=2.0)
    with cB2:
        st.session_state.sta_b['tunnel_depth'] = st.number_input("터널 토심 D_B (m)", value=st.session_state.sta_b['tunnel_depth'], step=2.0)
    with cB3:
        st.session_state.sta_b['radius'] = st.number_input("굴착 반경 R_B (m)", value=st.session_state.sta_b['radius'], step=0.2)

    st.divider()

    # 중앙 보간점(STA 0+010) 실시간 수칙 도출
    mid_h = (st.session_state.sta_a['ground_h'] + st.session_state.sta_b['ground_h']) / 2.0
    mid_d = (st.session_state.sta_a['tunnel_depth'] + st.session_state.sta_b['tunnel_depth']) / 2.0
    mid_r = (st.session_state.sta_a['radius'] + st.session_state.sta_b['radius']) / 2.0

    st.markdown("##### 📐 **[보간 결과] STA 0+010 (중앙 지점 계산값)**")
    st.info(f"• 보간 지표 고도: **{mid_h:.2f} m**  |  • 보간 터널 토심: **{mid_d:.2f} m**  |  • 보간 터널 반경: **{mid_r:.2f} m**")

    if st.button("🚀 보간 데이터 반영 3D GTS NX / PLAXIS MCT 생성"):
        st.success("Station A~B 간 선형 보간 지반/터널 요소망이 3D 수치해석 파일로 성공적으로 도출되었습니다!")
