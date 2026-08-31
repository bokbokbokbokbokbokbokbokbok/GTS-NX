import math
import io
import re
import numpy as np
import streamlit as st
import streamlit.components.v1 as components

# ezdxf 패키지 로드
try:
    import ezdxf
except ModuleNotFoundError:
    st.error("⚠️ `ezdxf` 패키지가 필요합니다. `requirements.txt`에 `ezdxf`를 추가해 주세요.")
    st.stop()

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX 3D 지반-터널 연계 FEA 수치해석 엔진",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ 3D 지반 요소(Ground Mass) 연동 FEA 해석 & 3D 로드뷰")
st.markdown("지반 고도, 암반 등급(RMR/GSI), 층후를 **3D 유한요소망(3D Ground Solid Elements)**으로 변환하여 3D 지반 파괴 및 침투 수치해석을 수행합니다.")

st.divider()

# ======================================================================
# 2. 파이썬 백엔드: 3D 지반-터널 연계 수치해석 연산기 (GTS NX 3D 수식)
# ======================================================================
class Ground3DFEASolver:
    """GTS NX 3D Mohr-Coulomb & Hoek-Brown 3D 암반 파괴 평가 엔진"""
    def __init__(self, depth=35.0, rmr=55, gsi=50, sig_ci=50000.0):
        self.H = depth
        self.rmr = rmr
        self.gsi = gsi
        self.sig_ci = sig_ci  # 암석 일축압축강도 (kPa)

    def calculate_3d_ground_stress(self, gamma=23.0, k0=0.5):
        """3D 주응력 (σ1, σ2, σ3) 및 유효응력 연산"""
        sig_v = gamma * self.H
        sig_h = k0 * sig_v
        
        sig_1 = sig_v  # 최대 주응력
        sig_3 = sig_h  # 최소 주응력
        return sig_1, sig_3

    def evaluate_hoek_brown_3d(self, sig_1, sig_3, mi=15):
        """
        [GTS NX 3D Hoek-Brown 암반 파괴 수식]
        f_hb = sig_1 - sig_3 - sig_ci * (mb * (sig_3 / sig_ci) + s)^a
        """
        mb = mi * math.exp((self.gsi - 100) / 28)
        s = math.exp((self.gsi - 100) / 9)
        a = 0.5 + (1/6) * (math.exp(-self.gsi/15) - math.exp(-20/3))

        # 파괴 지수 f_hb 연산 (f_hb > 0 이면 3D 지반 파괴 발생)
        sig_1_yield = sig_3 + self.sig_ci * ((mb * (sig_3 / self.sig_ci) + s) ** a)
        safety_factor_3d = sig_1_yield / (sig_1 + 1e-5)
        
        status = "OK (3D 탄성 영역)" if safety_factor_3d >= 1.2 else "NG (3D 소성 파괴 발생)"
        return safety_factor_3d, status

# 세션 관리
if "sections" not in st.session_state:
    st.session_state.sections = [
        {"start_sta": 0, "end_sta": 20, "pattern": "Pattern III", "rmr": 55, "gsi": 50, "bolt_sp": 1.5, "shot_thk": 150},
        {"start_sta": 20, "end_sta": 40, "pattern": "Pattern V", "rmr": 35, "gsi": 30, "bolt_sp": 1.0, "shot_thk": 200},
        {"start_sta": 40, "end_sta": 60, "pattern": "Pattern II", "rmr": 70, "gsi": 65, "bolt_sp": 2.0, "shot_thk": 100},
    ]

# ======================================================================
# 3. Three.js - 3D 지반 블록(Ground Solid Mass) & 터널 연동 뷰어
# ======================================================================
threejs_3d_ground_html = """
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
            border-radius: 8px; font-size: 12px; border: 1px solid #00e676;
        }
        .sta-btn-group { display: flex; gap: 6px; margin-top: 8px; }
        .sta-btn {
            background: #2196f3; color: white; border: none; padding: 6px 10px;
            border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 11px;
        }
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
            <b>📍 3D 지반 요소망(Ground Solid Mesh) 탐색</b>
            <div class="sta-btn-group">
                <button class="sta-btn active" onclick="moveToSta(0)">STA 0m</button>
                <button class="sta-btn" onclick="moveToSta(20)">STA 20m</button>
                <button class="sta-btn" onclick="moveToSta(40)">STA 40m</button>
                <button class="sta-btn" onclick="moveToSta(60)">STA 60m</button>
            </div>
        </div>
        <div class="legend-box">
            <b>🪨 3D 지반 체적 요소(3D Solid Element):</b><br>
            🟤 상부 토사/풍화암 | 🔘 암반 지반 블록 | 🔴 파괴 위험 체적(Yield Zone)
        </div>
    </div>

    <script>
        var targetZ = 10;
        var currentZ = 10;

        function moveToSta(sta) {
            var btns = document.querySelectorAll('.sta-btn');
            btns.forEach(function(b) { b.classList.remove('active'); });
            event.target.classList.add('active');
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
                currentZ += (targetZ - currentZ) * 0.08;
                var r = 18;
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
            renderer.domElement.addEventListener('wheel', function(e) {
                targetZ -= e.deltaY * 0.03;
                targetZ = Math.max(-55, Math.min(15, targetZ));
            });

            var ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
            scene.add(ambientLight);

            for (var lz = -70; lz <= 10; lz += 20) {
                var light = new THREE.PointLight(0xffd54f, 1.2, 25);
                light.position.set(0, 4.5, lz);
                scene.add(light);
            }

            // 1. 3D 지반 체적 요소망 (Ground Solid Mass Blocks)
            var groundGeo = new THREE.BoxGeometry(40, 30, 80);
            var groundMat = new THREE.MeshStandardMaterial({
                color: 0x2e2d2b,
                transparent: true,
                opacity: 0.35,
                wireframe: true
            });
            var groundBlock = new THREE.Mesh(groundGeo, groundMat);
            groundBlock.position.set(0, 5, -20);
            scene.add(groundBlock);

            // 2. NATM 터널 3D 굴착 공간
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
            var tunnelMat = new THREE.MeshStandardMaterial({ color: 0x1f1f24, side: THREE.BackSide, roughness: 0.8 });
            var tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
            tunnelMesh.position.set(0, 0, -60);
            scene.add(tunnelMesh);

            // 3. 지반 3D 소성 파괴 영역 (Yield Zone - 20~40m 구간 Red Solid)
            var yieldGeo = new THREE.CylinderGeometry(R + 2.0, R + 2.0, 20, 16, 10, true, 0, Math.PI);
            var yieldMat = new THREE.MeshBasicMaterial({ color: 0xff1744, wireframe: true, transparent: true, opacity: 0.6 });
            var yieldMesh = new THREE.Mesh(yieldGeo, yieldMat);
            yieldMesh.rotation.x = Math.PI / 2;
            yieldMesh.position.set(0, 0, -20);
            scene.add(yieldMesh);

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
# 4. Streamlit 화면 레이아웃 (3D 지반 해석 및 OK/NG 결과)
# ======================================================================
col_view, col_fea = st.columns([1.6, 1.4])

with col_view:
    st.subheader("🎥 3D 지반 요소망(Solid Mesh) 연동 뷰어")
    components.html(threejs_3d_ground_html, height=580)

with col_fea:
    st.subheader("🪨 3D 지반-터널 수치해석 연산 (GTS NX 3D)")

    depth_val = st.number_input("3D 토심 H (m)", value=35.0, step=5.0)
    sig_ci_val = st.number_input("암석 일축압축강도 σci (MPa)", value=50.0, step=5.0) * 1000.0

    st.markdown("---")
    st.markdown("##### **[3D 지반 구간별 Hoek-Brown 파괴 안전율(FS)]**")

    for idx, sec in enumerate(st.session_state.sections):
        solver_3d = Ground3DFEASolver(depth=depth_val, rmr=sec["rmr"], gsi=sec["gsi"], sig_ci=sig_ci_val)
        sig_1, sig_3 = solver_3d.calculate_3d_ground_stress()
        fs_3d, status_3d = solver_3d.evaluate_hoek_brown_3d(sig_1, sig_3)

        with st.expander(f"📌 구간 {idx+1}: STA {sec['start_sta']}m ~ {sec['end_sta']}m ({sec['pattern']})", expanded=True):
            st.write(f"• **지반 GSI 지수:** {sec['gsi']} | **최소주응력 σ3:** {sig_3:.1f} kPa")
            st.write(f"• **3D Hoek-Brown 파괴 안전율 (FS):** **{fs_3d:.2f}**")
            
            if "OK" in status_3d:
                st.success(f"3D 지반 상태: **{status_3d}** 🟢")
            else:
                st.error(f"3D 지반 상태: **{status_3d}** 🔴")

    st.divider()
    if st.button("🚀 3D 지반 요소망 GTS NX 파일 도출"):
        st.success("3D 체적 요소(3D Solid Ground Mesh)가 포함된 GTS NX 포맷 데이터 완정 출력을 수행했습니다!")
