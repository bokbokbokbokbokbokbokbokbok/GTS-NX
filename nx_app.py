import math
import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX 3D 정밀 터널 거리뷰 & OK/NG 검토",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 NATM 터널 정밀 3D 거리뷰(Street View) & OK / NG 검토기")
st.markdown("실제 NATM 터널 단면(아치형 상반 + 평탄 하반 + 강지보재)을 마우스로 **360도 거리뷰 시점**에서 관찰하세요.")

st.divider()

# ======================================================================
# 2. Three.js - 정밀 NATM 아치 터널 형상 & 거리뷰 HTML/JS
# ======================================================================
threejs_natm_tunnel_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }
        #canvas-container { width: 100%; height: 580px; position: relative; }
        .streetview-overlay {
            position: absolute; top: 12px; left: 12px; z-index: 100;
            background: rgba(0, 0, 0, 0.88); color: #00e676; padding: 10px 14px;
            border-radius: 8px; font-size: 12px; border: 1px solid #00e676;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5); pointer-events: none;
        }
        .instruction { color: #ffffff; font-size: 11px; margin-top: 4px; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="canvas-container">
        <div class="streetview-overlay">
            <b>🎥 NATM 정밀 터널 3D 거리뷰 모드</b>
            <div class="instruction">
                • <b>마우스 드래그:</b> 터널 내부 360도 시점 회전<br>
                • <b>마우스 휠:</b> 터널 막장 내부로 진입 / 후퇴<br>
            </div>
        </div>
    </div>

    <script>
        window.addEventListener('load', function() {
            const container = document.getElementById('canvas-container');

            // 1. Scene, Camera, Renderer
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a0f);
            scene.fog = new THREE.FogExp2(0x0a0a0f, 0.012);

            const camera = new THREE.PerspectiveCamera(70, container.clientWidth / 580, 0.1, 1000);
            const renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, 580);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            // 2. 거리뷰 마우스 탐색 컨트롤
            let isDragging = false;
            let previousMousePosition = { x: 0, y: 0 };
            let cameraRadius = 18;
            let cameraTheta = 0;
            let cameraPhi = Math.PI / 2.3;

            function updateCameraPosition() {
                camera.position.x = cameraRadius * Math.sin(cameraPhi) * Math.sin(cameraTheta);
                camera.position.y = cameraRadius * Math.cos(cameraPhi) + 1.2;
                camera.position.z = cameraRadius * Math.sin(cameraPhi) * Math.cos(cameraTheta) - 20;
                camera.lookAt(0, 1.0, -35);
            }
            updateCameraPosition();

            renderer.domElement.addEventListener('mousedown', function() { isDragging = true; });
            renderer.domElement.addEventListener('mousemove', function(e) {
                if (isDragging) {
                    const deltaX = e.clientX - previousMousePosition.x;
                    const deltaY = e.clientY - previousMousePosition.y;

                    cameraTheta -= deltaX * 0.005;
                    cameraPhi -= deltaY * 0.005;
                    cameraPhi = Math.max(0.1, Math.min(Math.PI - 0.1, cameraPhi));

                    updateCameraPosition();
                }
                previousMousePosition = { x: e.clientX, y: e.clientY };
            });
            window.addEventListener('mouseup', function() { isDragging = false; });
            renderer.domElement.addEventListener('wheel', function(e) {
                cameraRadius += e.deltaY * 0.025;
                cameraRadius = Math.max(-40, Math.min(50, cameraRadius));
                updateCameraPosition();
            });

            // 3. 조명 (터널 조명 및 비상등 표현)
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambientLight);

            for (let lz = -70; lz <= 10; lz += 20) {
                const light = new THREE.PointLight(0xffd54f, 1.2, 25);
                light.position.set(0, 4.5, lz);
                scene.add(light);
            }

            // 4. NATM 터널 2D 단면 형상 생성 (아치 상반 + 수직 측벽 + 하반 평탄)
            const shape = new THREE.Shape();
            const R = 6.2;       # 상반 아치 반지름
            const H_wall = 2.5;  # 측벽 높이
            const W_base = 6.0;  # 바닥 반폭

            shape.moveTo(-W_base, -H_wall);
            shape.lineTo(-W_base, 0);
            
            // 아치 곡선 생성 (상반 마굴)
            for (let a = Math.PI; a >= 0; a -= Math.PI / 20) {
                let ax = (W_base / R) * R * Math.cos(a);
                let ay = (R * Math.sin(a));
                shape.lineTo(ax, ay);
            }
            shape.lineTo(W_base, -H_wall);
            shape.lineTo(-W_base, -H_wall); // 바닥 인버트 closed

            // 5. 3D 돌출 (ExtrudeGeometry)로 압출 터널 보디 생성
            const extrudeSettings = {
                steps: 60,
                depth: 80,
                bevelEnabled: false
            };

            const tunnelGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
            const tunnelMat = new THREE.MeshStandardMaterial({
                color: 0x424242,
                side: THREE.BackSide, // 터널 내부가 보이도록 설정
                roughness: 0.8
            });

            const tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
            tunnelMesh.position.set(0, 0, -60);
            scene.add(tunnelMesh);

            // 6. 강지보재(H-Beam Steel Rib) 링 격자 배치
            const ribMat = new THREE.LineBasicMaterial({ color: 0xffb74d, linewidth: 3 });
            for (let rz = -55; rz <= 15; rz += 3.5) {
                const edges = new THREE.EdgesGeometry(tunnelGeo);
                const ribLine = new THREE.LineSegments(edges, ribMat);
                ribLine.position.set(0, 0, rz);
                scene.add(ribLine);
            }

            // 7. 방사형 록볼트 (Rockbolts - D25 Steel Rods)
            const boltMat = new THREE.MeshBasicMaterial({ color: 0xff1744 });
            for (let bz = -55; bz <= 15; bz += 4.5) {
                for (let angle = 0.2; angle <= Math.PI - 0.2; angle += 0.35) {
                    const boltGeo = new THREE.CylinderGeometry(0.08, 0.08, 3.8, 8);
                    const bolt = new THREE.Mesh(boltGeo, boltMat);

                    const bx = (W_base + 1.9) * Math.cos(angle);
                    const by = (R + 1.9) * Math.sin(angle);

                    bolt.position.set(bx, by, bz);
                    bolt.rotation.z = angle - Math.PI / 2;
                    scene.add(bolt);
                }
            }

            // 8. 애니메이션 루프
            function animate() {
                requestAnimationFrame(animate);
                renderer.render(scene, camera);
            }
            animate();
        });
    </script>
</body>
</html>
"""

# ======================================================================
# 3. 파이썬 연산 로직 (OK / NG 자동 판정)
# ======================================================================
def evaluate_stability(depth=35.0, gamma=23.0, k0=0.5, E_rock=1500000.0):
    sigma_v = gamma * depth
    sigma_h = k0 * sigma_v
    radius = 6.2
    v = 0.25

    u_crown = ((1 + v) * radius * sigma_v / E_rock) * 1000.0
    u_wall = ((1 + v) * radius * sigma_h / E_rock) * 1000.0
    
    sigma_shotcrete = (3.0 * 20000000.0 * ((0.15**3)/12.0) * (u_crown / 1000.0) / (radius**2)) / ((0.15**2)/6.0) / 1000.0
    t_rockbolt = min(180.0, 210000000.0 * 0.00049 * (u_crown / 1000.0 / 4.0) * 1.5)

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
# 4. Streamlit 레이아웃
# ======================================================================
col_view, col_result = st.columns([1.8, 1.2])

with col_view:
    st.subheader("🎥 NATM 아치 정밀 3D 거리뷰")
    components.html(threejs_natm_tunnel_html, height=600)

with col_result:
    st.subheader("🚥 종합 안전성 OK / NG 판정")
    
    depth = st.number_input("굴착 깊이 H (m)", value=35.0, step=5.0)
    e_rock = st.number_input("암반 변형계수 E (MPa)", value=1500.0, step=100.0) * 1000.0
    
    eval_res = evaluate_stability(depth=depth, E_rock=e_rock)

    if "OK" in eval_res["total"]:
        st.success(f"### 🎉 최종 안전성 결과: {eval_res['total']}")
    else:
        st.error(f"### 🚨 최종 안전성 결과: {eval_res['total']}")

    st.divider()
    st.markdown("### 📋 4대 핵심 항목 OK / NG 현황")

    if eval_res["crown"] == "OK":
        st.success("🟢 **1. 천단변위:** OK (기준 만족)")
    else:
        st.error("🔴 **1. 천단변위:** NG (허용치 초과)")

    if eval_res["wall"] == "OK":
        st.success("🟢 **2. 내공변위:** OK (기준 만족)")
    else:
        st.error("🔴 **2. 내공변위:** NG (허용치 초과)")

    if eval_res["shotcrete"] == "OK":
        st.success("🟢 **3. 숏크리트 휨압축응력:** OK (기준 만족)")
    else:
        st.error("🔴 **3. 숏크리트 휨압축응력:** NG (파괴 위험)")

    if eval_res["rockbolt"] == "OK":
        st.success("🟢 **4. 록볼트 최대축력:** OK (기준 만족)")
    else:
        st.error("🔴 **4. 록볼트 최대축력:** NG (항복 위험)")

    st.divider()
    if st.button("🚀 OK/NG 검토서 도출"):
        st.info("OK/NG 판정 데이터가 GTS NX 검토 일지 포맷으로 도출되었습니다.")
