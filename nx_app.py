import math
import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX 3D 거리뷰 모식도 & OK/NG 안전성 검토",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 3D 거리뷰(Street View) 터널 모식화 & OK / NG 검토기")
st.markdown("마우스와 키보드로 **거리뷰처럼 3D 공간 내부를 360도 탐색**하고 구조 안전성(OK/NG)을 직관적으로 확인하세요.")

st.divider()

# ======================================================================
# 2. Three.js 기반 3D 거리뷰 뷰어 HTML/JS
# ======================================================================
threejs_streetview_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; overflow: hidden; font-family: sans-serif; }
        #canvas-container { width: 100%; height: 580px; position: relative; }
        .streetview-overlay {
            position: absolute; top: 12px; left: 12px; z-index: 100;
            background: rgba(0, 0, 0, 0.85); color: #00e676; padding: 10px 14px;
            border-radius: 8px; font-size: 12px; border: 1px solid #00e676;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }
        .instruction { color: #ffffff; font-size: 11px; margin-top: 4px; }
    </style>
    <!-- Three.js 3D 라이브러리 및 OrbitControls -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="canvas-container">
        <div class="streetview-overlay">
            <b>🎥 3D 거리뷰(First-Person View) 모드</b>
            <div class="instruction">
                • <b>마우스 드래그:</b> 360도 화면 회전<br>
                • <b>휠 스크롤:</b> 줌 인 / 줌 아웃 (터널 내부 진입 가능)<br>
                • <b>우클릭 드래그:</b> 시점 이동 (Pan)
            </div>
        </div>
    </div>

    <script>
        const container = document.getElementById('canvas-container');

        // 1. Scene, Camera, Renderer 생성 (투영 카메라로 거리뷰 구현)
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x111118);
        scene.fog = new THREE.FogExp2(0x111118, 0.015);

        const camera = new THREE.PerspectiveCamera(75, container.clientWidth / 580, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(container.clientWidth, 580);
        renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(renderer.domElement);

        // 2. 거리뷰 조종기 (OrbitControls)
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // 초기 카메라 위치 (터널 입구 바로 앞 - 거리뷰 시점)
        camera.position.set(0, 1.5, 25);
        controls.target.set(0, 0, -20);
        controls.update();

        # 3. 조명 (Light)
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const pointLight = new THREE.PointLight(0xffeb3b, 1.5, 50);
        pointLight.position.set(0, 4, 0);
        scene.add(pointLight);

        // 4. 지표면 그리드 (Ground)
        const gridHelper = new THREE.GridHelper(100, 40, 0x444444, 0x222222);
        gridHelper.position.y = -3;
        scene.add(gridHelper);

        // 5. 3D 터널 라이너 (원통형 메시)
        const tunnelRadius = 6.5;
        const tunnelLength = 80;
        const tunnelGeo = new THREE.CylinderGeometry(tunnelRadius, tunnelRadius, tunnelLength, 32, 40, true, 0, Math.PI);
        const tunnelMat = new THREE.MeshStandardMaterial({
            color: 0x37474f,
            side: THREE.DoubleSide,
            wireframe: false,
            roughness: 0.6
        });
        const tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
        tunnelMesh.rotation.x = Math.PI / 2;
        tunnelMesh.position.set(0, 0, -20);
        scene.add(tunnelMesh);

        // 터널 격자 와이어프레임 강조
        const wireframeGeo = new THREE.WireframeGeometry(tunnelGeo);
        const wireframeMat = new THREE.LineBasicMaterial({ color: 0x2196f3, linewidth: 1 });
        const wireframe = new THREE.LineSegments(wireframeGeo, wireframeMat);
        wireframe.rotation.x = Math.PI / 2;
        wireframe.position.set(0, 0, -20);
        scene.add(wireframe);

        // 6. 3D 록볼트 방사형 보강재 (Red Rods)
        const boltMat = new THREE.MeshBasicMaterial({ color: 0xff1744 });
        for (let z = -55; z <= 15; z += 6) {
            for (let angle = 0.3; angle <= Math.PI - 0.3; angle += 0.45) {
                const boltGeo = new THREE.CylinderGeometry(0.1, 0.1, 3.5, 8);
                const bolt = new THREE.Mesh(boltGeo, boltMat);
                
                const bx = (tunnelRadius + 1.75) * Math.cos(angle);
                const by = (tunnelRadius + 1.75) * Math.sin(angle);
                
                bolt.position.set(bx, by - 3, z);
                bolt.rotation.z = angle - Math.PI / 2;
                scene.add(bolt);
            }
        }

        // 7. 애니메이션 루프 (거리뷰 실시간 렌더링)
        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = container.clientWidth / 580;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, 580);
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
    radius = 6.5
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
# 4. Streamlit 화면 레이아웃
# ======================================================================
col_view, col_result = st.columns([1.8, 1.2])

with col_view:
    st.subheader("🎥 3D 거리뷰(Street View) 실시간 모식도")
    components.html(threejs_streetview_html, height=600)

with col_result:
    st.subheader("🚥 종합 안전성 OK / NG 판정")
    
    depth = st.number_input("굴착 깊이 H (m)", value=35.0, step=5.0)
    e_rock = st.number_input("암반 변형계수 E (MPa)", value=1500.0, step=100.0) * 1000.0
    
    eval_res = evaluate_stability(depth=depth, E_rock=e_rock)

    # 최종 상태 판정 메인 배너
    if "OK" in eval_res["total"]:
        st.success(f"### 🎉 최종 안전성 결과: {eval_res['total']}")
    else:
        st.error(f"### 🚨 최종 안전성 결과: {eval_res['total']}")

    st.divider()
    st.markdown("### 📋 4대 핵심 항목 OK / NG 현황")

    # 1. 천단변위
    if eval_res["crown"] == "OK":
        st.success("🟢 **1. 천단변위:** OK (기준 만족)")
    else:
        st.error("🔴 **1. 천단변위:** NG (허용치 초과)")

    # 2. 내공변위
    if eval_res["wall"] == "OK":
        st.success("🟢 **2. 내공변위:** OK (기준 만족)")
    else:
        st.error("🔴 **2. 내공변위:** NG (허용치 초과)")

    # 3. 숏크리트 휨응력
    if eval_res["shotcrete"] == "OK":
        st.success("🟢 **3. 숏크리트 휨압축응력:** OK (기준 만족)")
    else:
        st.error("🔴 **3. 숏크리트 휨압축응력:** NG (파괴 위험)")

    # 4. 록볼트 축력
    if eval_res["rockbolt"] == "OK":
        st.success("🟢 **4. 록볼트 최대축력:** OK (기준 만족)")
    else:
        st.error("🔴 **4. 록볼트 최대축력:** NG (항복 위험)")

    st.divider()
    if st.button("🚀 OK/NG 검토서 출력"):
        st.info("OK/NG 판정 데이터가 GTS NX 검토 일지 포맷으로 도출되었습니다.")
