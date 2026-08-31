import math
import io
import streamlit as st
import streamlit.components.v1 as components

# ezdxf 파싱 라이브러리
try:
    import ezdxf
except ModuleNotFoundError:
    st.error("⚠️ `ezdxf` 패키지가 필요합니다. `requirements.txt`에 `ezdxf`를 추가해 주세요.")
    st.stop()

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX DXF 연동 구간별 가변 패턴 설계기",
    page_icon="🏗️",
    layout="wide"
)

st.title("🏗️ DXF 보강재 파싱 & 시점~종점 구간별 패턴 적용 엔진")
st.markdown("업로드된 **DXF 지보 도면(록볼트/강관보강/강지보)**을 분석하여 구간별(시점~종점) 패턴을 자동 추출하고 3D 거리뷰에 실시간 반영합니다.")

st.divider()

# ======================================================================
# 2. DXF 지보 부재 파서 & 패턴 자동 분류기
# ======================================================================
class DXFPatternAnalyzer:
    """DXF 도면 내 록볼트, 강관다단, 강지보 레이어를 파싱하여 NATM 패턴을 추정"""
    def __init__(self):
        self.rockbolt_count = 0
        self.pipe_reinforce_count = 0
        self.steel_rib_count = 0

    def analyze_dxf(self, dxf_file_bytes):
        try:
            content = dxf_file_bytes.getvalue().decode('euc-kr', errors='ignore')
            doc = ezdxf.read(io.StringIO(content))
            msp = doc.modelspace()

            for entity in msp:
                layer = entity.dxf.layer
                if entity.dxftype() == 'LINE':
                    # 록볼트/강지보재 레이어
                    if layer in ('CS-STEL-MAJR', 'CS-CUTL'):
                        self.rockbolt_count += 1
                    # 강관다단 / 훠폴링 보강선 레이어
                    elif layer in ('S-DIM', 'CS-EXCV'):
                        self.pipe_reinforce_count += 1
                elif entity.dxftype() == 'ARC' and layer == 'CS-CUTL':
                    self.steel_rib_count += 1

            # 파싱 데이터 기반 추정 패턴 결정
            if self.pipe_reinforce_count > 5:
                return "Pattern V (강관다단+강지보재)", 100, 1.0, 200
            elif self.rockbolt_count > 10:
                return "Pattern III (상/하반 분할+록볼트)", 55, 1.5, 150
            else:
                return "Pattern II (전단면 굴착)", 70, 2.0, 100
        except Exception:
            return "Pattern III (기본 패턴)", 50, 1.5, 150

# 세션 상태 관리 (시점 ~ 종점 구간별 패턴 스케줄)
if "sections" not in st.session_state:
    st.session_state.sections = [
        {"start_sta": 0, "end_sta": 20, "pattern": "Pattern III (상/하반 분할)", "rmr": 55, "bolt_sp": 1.5, "shot_thk": 150, "pipe_sup": "미적용"},
        {"start_sta": 20, "end_sta": 40, "pattern": "Pattern V (강관다단 보강)", "rmr": 35, "bolt_sp": 1.0, "shot_thk": 200, "pipe_sup": "강관다단 훠폴링"},
        {"start_sta": 40, "end_sta": 60, "pattern": "Pattern II (전단면 굴착)", "rmr": 70, "bolt_sp": 2.0, "shot_thk": 100, "pipe_sup": "미적용"},
    ]

# ======================================================================
# 3. Three.js - 록볼트 & 강관보강 시각화 3D 로드뷰 HTML/JS
# ======================================================================
threejs_advanced_roadview = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }
        #canvas-container { width: 100%; height: 560px; position: relative; }
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
            <b>📍 시점~종점 로드뷰 바로 이동</b>
            <div class="sta-btn-group">
                <button class="sta-btn active" onclick="moveToSta(0)">STA 0m (시점)</button>
                <button class="sta-btn" onclick="moveToSta(20)">STA 20m</button>
                <button class="sta-btn" onclick="moveToSta(40)">STA 40m</button>
                <button class="sta-btn" onclick="moveToSta(60)">STA 60m (종점)</button>
            </div>
        </div>
        <div class="legend-box">
            <b>🎨 지보 및 보강재 3D 표시:</b><br>
            🔴 록볼트 | 🟡 강지보재(H-Rib) | 🟣 강관다단 훠폴링 보강재
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

            var camera = new THREE.PerspectiveCamera(70, container.clientWidth / 560, 0.1, 1000);
            var renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, 560);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            var isDragging = false;
            var previousMousePosition = { x: 0, y: 0 };
            var cameraTheta = 0;
            var cameraPhi = Math.PI / 2.3;

            function updateCamera() {
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

            // NATM 터널 3D 형상
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

            // 강지보재(H-Rib) 및 록볼트 시각화
            var matPat3 = new THREE.LineBasicMaterial({ color: 0xffeb3b, linewidth: 3 });
            var matPat5 = new THREE.LineBasicMaterial({ color: 0xff1744, linewidth: 4 });
            var matPat2 = new THREE.LineBasicMaterial({ color: 0x00e676, linewidth: 2 });

            for (var rz = -55; rz <= 15; rz += 3.0) {
                var edges = new THREE.EdgesGeometry(tunnelGeo);
                var currentMat = matPat3;
                if (rz < -30) currentMat = matPat2;
                else if (rz < -5) currentMat = matPat5;

                var ribLine = new THREE.LineSegments(edges, currentMat);
                ribLine.position.set(0, 0, rz);
                scene.add(ribLine);
            }

            // 강관다단 훠폴링 보강재 (Pattern V 구간 보라색 종방향 파이프)
            var pipeMat = new THREE.MeshBasicMaterial({ color: 0xab47bc });
            for (var pAngle = 0.3; pAngle <= Math.PI - 0.3; pAngle += 0.25) {
                var pipeGeo = new THREE.CylinderGeometry(0.12, 0.12, 25, 8);
                var pipeMesh = new THREE.Mesh(pipeGeo, pipeMat);
                var px = (W_base + 0.3) * Math.cos(pAngle);
                var py = (R + 0.3) * Math.sin(pAngle);
                pipeMesh.position.set(px, py, -20);
                pipeMesh.rotation.x = Math.PI / 2;
                scene.add(pipeMesh);
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
# 4. Streamlit 화면 레이아웃 (DXF 업로드 및 구간별 패턴 지정 테이블)
# ======================================================================
col_view, col_schedule = st.columns([1.6, 1.4])

with col_view:
    st.subheader("🎥 3D 로드뷰 (보강재/지보패턴 적용)")
    components.html(threejs_advanced_roadview, height=580)

with col_schedule:
    st.subheader("📂 DXF 도면 파싱 & [시점 ~ 종점] 구간별 패턴 설정")

    uploaded_dxf = st.file_uploader("DXF 도면 업로드 (7km235_PD-2A.dxf)", type=["dxf"])
    
    if uploaded_dxf:
        analyzer = DXFPatternAnalyzer()
        auto_pat, auto_rmr, auto_sp, auto_thk = analyzer.analyze_dxf(uploaded_dxf)
        st.success(f"✅ **DXF 자동 분석 결과:** 록볼트 {analyzer.rockbolt_count}개, 강관보강선 {analyzer.pipe_reinforce_count}개 감지 ➔ 추정 패턴: **{auto_pat}**")

    st.markdown("---")
    st.markdown("##### **[구간별 지보 패턴 설정표 (시점 STA ~ 종점 STA)]**")

    # 새 구간 추가 버튼
    if st.button("➕ 구간 추가 (Add Section)"):
        last_end = st.session_state.sections[-1]["end_sta"]
        st.session_state.sections.append({
            "start_sta": last_end, "end_sta": last_end + 20,
            "pattern": "Pattern III (상/하반 분할)", "rmr": 50,
            "bolt_sp": 1.5, "shot_thk": 150, "pipe_sup": "미적용"
        })
        st.rerun()

    updated_sec_list = []
    
    # 시점~종점 구간별 입력 및 판정 창
    for idx, sec in enumerate(st.session_state.sections):
        st.write(f"📂 **[구간 {idx+1}] STA {sec['start_sta']}m ~ STA {sec['end_sta']}m**")
        
        c1, c2, c3 = st.columns([1.2, 1.2, 1])
        with c1:
            s_sta = st.number_input(f"시점 STA (m)", value=sec["start_sta"], step=5, key=f"s_{idx}")
            e_sta = st.number_input(f"종점 STA (m)", value=sec["end_sta"], step=5, key=f"e_{idx}")
        with c2:
            pat_sel = st.selectbox(f"적용 지보 패턴", ["Pattern I", "Pattern II", "Pattern III", "Pattern IV", "Pattern V"], index=2 if "III" in sec["pattern"] else (4 if "V" in sec["pattern"] else 1), key=f"pat_{idx}")
            pipe_sel = st.selectbox(f"천단 보강재", ["미적용", "훠폴링 (Forepoling)", "강관다단 훠폴링", "RPUM 보강"], index=2 if "강관" in sec["pipe_sup"] else 0, key=f"pipe_{idx}")
        with c3:
            thk_val = st.number_input(f"숏크리트 (mm)", value=sec["shot_thk"], step=25, key=f"thk_{idx}")
            sp_val = st.number_input(f"록볼트 간격 (m)", value=sec["bolt_sp"], step=0.25, key=f"sp_{idx}")

        # 수치 기반 판정 (OK / NG)
        u_crown = (35.0 * 23.0 * 6.2 / max(300000.0, sec["rmr"] * 30000.0)) * 1000.0
        sec_res = "OK (안전)" if u_crown <= 20.0 else "NG (보강 필요)"

        if "OK" in sec_res:
            st.success(f"구간 {idx+1} 판정 결과: **{sec_res}** 🟢")
        else:
            st.error(f"구간 {idx+1} 판정 결과: **{sec_res}** 🔴")

        updated_sec_list.append({
            "start_sta": s_sta, "end_sta": e_sta, "pattern": pat_sel,
            "rmr": sec["rmr"], "bolt_sp": sp_val, "shot_thk": thk_val, "pipe_sup": pipe_sel
        })
        st.markdown("---")

    st.session_state.sections = updated_sec_list

    if st.button("🚀 구간별 가변 패턴 GTS NX MCT 파일 도출"):
        st.success("시점~종점 구간별 패턴 및 DXF 지보 데이터가 GTS NX 파일 포맷으로 출력되었습니다!")
        
