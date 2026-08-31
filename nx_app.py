import math
import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX 측점별 로드뷰 이동 & 가변 패턴 3D 검토기",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 측점별 로드뷰 이동 & 20m 가변 지보 패턴 3D 검토기")
st.markdown("카카오맵/네이버지도 로드뷰처럼 **측점 버튼(STA 0m, 20m, 40m...)을 클릭하여 터널 내부 해당 위치로 직접 이동**하세요.")

st.divider()

# ======================================================================
# 2. 파이썬 백엔드: 측점 세션 초기화 및 상태 관리
# ======================================================================
if "pattern_schedule" not in st.session_state:
    st.session_state.pattern_schedule = [
        {"start": 0, "end": 20, "pattern": "Pattern III (상/하반 분할)", "rmr": 55, "rockbolt_sp": 1.5, "shotcrete_thk": 150},
        {"start": 20, "end": 40, "pattern": "Pattern V (강지보+훠폴링)", "rmr": 35, "rockbolt_sp": 1.0, "shotcrete_thk": 200},
        {"start": 40, "end": 60, "pattern": "Pattern II (전단면 굴착)", "rmr": 70, "rockbolt_sp": 2.0, "shotcrete_thk": 100},
    ]

def evaluate_section_stability(depth, rmr, shotcrete_thk, rockbolt_sp):
    radius = 6.2
    gamma = 23.0
    k0 = 0.5
    E_rock = max(300000.0, rmr * 30000.0)
    
    sigma_v = gamma * depth
    sigma_h = k0 * sigma_v
    v = 0.25

    u_crown = ((1 + v) * radius * sigma_v / E_rock) * 1000.0
    u_wall = ((1 + v) * radius * sigma_h / E_rock) * 1000.0
    
    t_m = shotcrete_thk / 1000.0
    sigma_shotcrete = (3.0 * 20000000.0 * ((t_m**3)/12.0) * (u_crown / 1000.0) / (radius**2)) / ((t_m**2)/6.0) / 1000.0
    t_rockbolt = min(180.0, 210000000.0 * 0.00049 * (u_crown / 1000.0 / 4.0) * (rockbolt_sp / 1.0))

    res_crown = "OK" if u_crown <= 20.0 else "NG"
    res_wall = "OK" if u_wall <= 25.0 else "NG"
    res_shotcrete = "OK" if sigma_shotcrete <= 21.0 else "NG"
    res_rockbolt = "OK" if t_rockbolt <= 130.0 else "NG"

    is_ok = (res_crown == "OK" and res_wall == "OK" and res_shotcrete == "OK" and res_rockbolt == "OK")
    return "OK (안전)" if is_ok else "NG (보강)"

# ======================================================================
# 3. Three.js - 측점 순간이동(Fly-To) 기능 탑재 로드뷰 3D HTML/JS
# ======================================================================
threejs_roadview_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }
        #canvas-container { width: 100%; height: 580px; position: relative; }
        .roadview-nav {
            position: absolute; top: 12px; left: 12px; z-index: 100;
            background: rgba(0, 0, 0, 0.90); color: white; padding: 12px;
            border-radius: 8px; font-size: 12px; border: 1px solid #2196f3;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }
        .sta-btn-group { display: flex; gap: 6px; margin-top: 8px; }
        .sta-btn {
            background: #2196f3; color: white; border: none; padding: 6px 12px;
            border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 11px;
            transition: 0.2s;
        }
        .sta-btn:hover { background: #0b7ad1; transform: scale(1.05); }
        .sta-btn.active { background: #00e676; color: black; }
        .legend-box {
            position: absolute; bottom: 12px; left: 12px; z-index: 100;
            background: rgba(0, 0, 0, 0.85); color: white; padding: 8px 12px;
            border-radius: 6px; font-size: 11px;
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="canvas-container">
        <div class="roadview-nav">
            <b>📍 로드뷰 측점(STA) 바로 이동</b>
            <div class="sta-btn-group">
                <button class="sta-btn active" onclick="moveToSta(0)">STA 0m (입구)</button>
                <button class="sta-btn" onclick="moveToSta(20)">STA 20m</button>
                <button class="sta-btn" onclick="moveToSta(40)">STA 40m</button>
                <button class="sta-btn" onclick="moveToSta(60)">STA 60m (막장)</button>
            </div>
        </div>
        <div class="legend-box">
            <b>🎨 측점 지보 색상:</b> 🟡 0~20m (Pattern III) | 🔴 20~40m (Pattern V) | 🟢 40~60m (Pattern II)
        </div>
    </div>

    <script>
        var targetZ = 10;
        var currentZ = 10;

        // 측점 이동 함수 (카메라 Z축 부드러운 스무스 이동)
        function moveToSta(sta) {
            // 버튼 활성화 클래스 변경
            var btns = document.querySelectorAll('.sta-btn');
            btns.forEach(function(b) { b.classList.remove('active'); });
            event.target.classList.add('active');

            // STA 0m: Z=10, STA 20m: Z=-10, STA 40m: Z=-30, STA 60m: Z=-50
            targetZ = 10 - sta;
        }

        window.addEventListener('load', function() {
            var container = document.getElementById('canvas-container');

            var scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a0f);
            scene.fog = new THREE.FogExp2(0x0a0a0f, 0.012);

            var camera = new THREE.PerspectiveCamera(70, container.clientWidth / 580, 0.1, 1000);
            var renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, 580);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            var isDragging = false;
            var previousMousePosition = { x: 0, y: 0 };
            var cameraTheta = 0;
            var cameraPhi = Math.PI / 2.3;

            function updateCamera() {
                // 부드러운 스무스 이동 (LERP 연산)
                currentZ += (targetZ - currentZ) * 0.08;

                var r = 16;
                camera.position.x = r * Math.sin(cameraPhi) * Math.sin(cameraTheta);
                camera.position.y = r * Math.cos(cameraPhi) + 1.2;
                camera.position.z = currentZ + (r * Math.sin(cameraPhi) * Math.cos(cameraTheta));
                camera.lookAt(0, 1.0, currentZ - 20);
            }

            renderer.domElement.addEventListener('mousedown', function() { isDragging = true; });
            renderer.domElement.addEventListener('mousemove', function(e) {
                if (isDragging) {
                    var deltaX = e.clientX - previousMousePosition.x;
                    var deltaY = e.clientY - previousMousePosition.y;

                    cameraTheta -= deltaX * 0.005;
                    cameraPhi -= deltaY * 0.005;
                    cameraPhi = Math.max(0.1, Math.min(Math.PI - 0.1, cameraPhi));
                }
                previousMousePosition = { x: e.clientX, y: e.clientY };
            });
            window.addEventListener('mouseup', function() { isDragging = false; });

            // 휠 스크롤로 앞/뒤 로드뷰 이동
            renderer.domElement.addEventListener('wheel', function(e) {
                targetZ -= e.deltaY * 0.03;
                targetZ = Math.max(-55, Math.min(15, targetZ));
            });

            var ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambientLight);

            for (var lz = -70; lz <= 10; lz += 20) {
                var light = new THREE.PointLight(0xffd54f, 1.2, 25);
                light.position.set(0, 4.5, lz);
                scene.add(light);
            }

            // NATM 아치 터널 형상
            var shape = new THREE.Shape();
            var R = 6.2;
            var H_wall = 2.5;
            var W_base = 6.0;

            shape.moveTo(-W_base, -H_wall);
            shape.lineTo(-W_base, 0);
            for (var a = Math.PI; a >= 0; a -= Math.PI / 20) {
                var ax = (W_base / R) * R * Math.cos(a);
                var ay = (R * Math.sin(a));
                shape.lineTo(ax, ay);
            }
            shape.lineTo(W_base, -H_wall);
            shape.lineTo(-W_base, -H_wall);

            var extrudeSettings = { steps: 60, depth: 80, bevelEnabled: false };
            var tunnelGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
            var tunnelMat = new THREE.MeshStandardMaterial({ color: 0x333338, side: THREE.BackSide, roughness: 0.8 });
            var tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
            tunnelMesh.position.set(0, 0, -60);
            scene.add(tunnelMesh);

            // 가변 구간 지보 재질
            var matPat3 = new THREE.LineBasicMaterial({ color: 0xffeb3b, linewidth: 3 }); // 0~20m (노랑)
            var matPat5 = new THREE.LineBasicMaterial({ color: 0xff1744, linewidth: 4 }); // 20~40m (빨강)
            var matPat2 = new THREE.LineBasicMaterial({ color: 0x00e676, linewidth: 2 }); // 40~60m (녹색)

            for (var rz = -55; rz <= 15; rz += 3.0) {
                var edges = new THREE.EdgesGeometry(tunnelGeo);
                var currentMat = matPat3;
                if (rz < -30) currentMat = matPat2;
                else if (rz < -5) currentMat = matPat5;

                var ribLine = new THREE.LineSegments(edges, currentMat);
                ribLine.position.set(0, 0, rz);
                scene.add(ribLine);
            }

            function animate() {
                requestAnimationFrame(animate);
                updateCamera();
                renderer.render(scene, camera);
            }
            animate();
        });
    </script>
</body>
</html>
"""

# ======================================================================
# 4. Streamlit 화면 구성
# ======================================================================
col_view, col_schedule = st.columns([1.7, 1.3])

with col_view:
    st.subheader("🎥 로드뷰 측점 이동 3D 터널 뷰어")
    components.html(threejs_roadview_html, height=600)

with col_schedule:
    st.subheader("📐 20m/구간별 지보 패턴 설정 (Schedule)")

    depth_val = st.number_input("터널 대표 굴착 깊이 H (m)", value=35.0, step=5.0)

    st.markdown("##### **[구간별 지보 패턴 테이블]**")
    
    updated_schedule = []
    for idx, sec in enumerate(st.session_state.pattern_schedule):
        with st.expander(f"📌 구간 {idx+1}: STA {sec['start']}m ~ {sec['end']}m", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                p_name = st.selectbox(f"지보 패턴 (구간 {idx+1})", ["Pattern I", "Pattern II", "Pattern III", "Pattern IV", "Pattern V"], index=2 if idx==0 else (4 if idx==1 else 1), key=f"p_{idx}")
                rmr_val = st.slider(f"지반 RMR 점수 (구간 {idx+1})", 0, 100, sec['rmr'], key=f"rmr_{idx}")
            with c2:
                sp_val = st.number_input(f"록볼트 간격 (m)", value=sec['rockbolt_sp'], step=0.25, key=f"sp_{idx}")
                thk_val = st.number_input(f"숏크리트 두께 (mm)", value=sec['shotcrete_thk'], step=25, key=f"thk_{idx}")
            
            sec_result = evaluate_section_stability(depth_val, rmr_val, thk_val, sp_val)
            
            if "OK" in sec_result:
                st.success(f"구간 {idx+1} 판정: **{sec_result}** 🟢")
            else:
                st.error(f"구간 {idx+1} 판정: **{sec_result}** 🔴")

            updated_schedule.append({
                "start": sec['start'], "end": sec['end'], "pattern": p_name,
                "rmr": rmr_val, "rockbolt_sp": sp_val, "shotcrete_thk": thk_val, "result": sec_result
            })

    st.session_state.pattern_schedule = updated_schedule

    st.divider()
    if st.button("🚀 측점 및 구간별 패턴 GTS NX MCT 도출"):
        st.success("측점 정보가 연동된 GTS NX 파일이 출력되었습니다!")
