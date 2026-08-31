import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="AI Agent & PLAXIS Style 3D Cloud Engine",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI 에이전트 연동 & PLAXIS 스타일 3D 클라우드 해석기")
st.markdown("자연어 명령어 또는 AI 에이전트를 통해 **3D 지반 메쉬(Solid Mesh), 파괴 영역, OK/NG 판정**을 웹상에서 실시간으로 구동합니다.")

st.divider()

# ======================================================================
# 2. 웹 브라우저 단 AI 에이전트 + Three.js 3D PLAXIS Engine (HTML/JS)
# ======================================================================
ai_plaxis_web_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }
        #app-container { display: flex; width: 100%; height: 600px; }
        #canvas-container { flex: 2; position: relative; height: 100%; }
        #ai-panel { flex: 1; background: #14141e; color: white; padding: 16px; display: flex; flex-direction: column; border-left: 1px solid #333; }
        
        .ai-title { color: #00e676; font-size: 14px; font-weight: bold; margin-bottom: 8px; }
        .ai-chat-box { flex: 1; background: #0a0a0f; border-radius: 6px; padding: 10px; overflow-y: auto; font-size: 11px; font-family: monospace; border: 1px solid #2a2a35; }
        .ai-msg { margin-bottom: 8px; line-height: 1.4; }
        .user-msg { color: #2196f3; }
        .agent-msg { color: #00e676; }
        .plaxis-code { color: #ffeb3b; }
        
        .ai-input-group { display: flex; gap: 6px; margin-top: 8px; }
        .ai-input { flex: 1; background: #1a1a24; border: 1px solid #333; color: white; padding: 8px; border-radius: 4px; font-size: 11px; }
        .ai-btn { background: #2196f3; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 11px; }
        .ai-btn:hover { background: #0b7ad1; }
        
        .status-badge { background: #ff1744; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block; margin-top: 6px; }
        .status-ok { background: #00e676; color: black; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="app-container">
        <!-- 3D PLAXIS 스타일 렌더링 뷰어 -->
        <div id="canvas-container"></div>

        <!-- AI 에이전트 제어 및 API 통신 패널 -->
        <div id="ai-panel">
            <div class="ai-title">🤖 AI Agent & Cloud FEA Pipeline</div>
            <div style="font-size: 11px; color: #aaa; margin-bottom: 8px;">
                PLAXIS API / iTwin Cloud AI 연동 모뮬
            </div>
            
            <div class="ai-chat-box" id="chatBox">
                <div class="ai-msg agent-msg">[System] AI 클라우드 해석 에이전트 준비 완료.</div>
                <div class="ai-msg agent-msg">[System] 자연어 명령을 입력하거나 [AI 수치해석 구동] 버튼을 누르세요.</div>
            </div>

            <div class="ai-input-group">
                <input type="text" id="aiInput" class="ai-input" placeholder="예: STA 20m~40m 지반 연약화 반영 해석해줘" value="STA 20m~40m 파괴 영역 분석 및 PLAXIS 연산 구동">
                <button class="ai-btn" onclick="runAiAgent()">전송</button>
            </div>
        </div>
    </div>

    <script>
        var scene, camera, renderer;
        var groundMesh, yieldZoneMesh;
        var targetZ = 10, currentZ = 10;

        window.addEventListener('load', function() {
            var container = document.getElementById('canvas-container');

            // 1. Three.js 3D Scene 설정
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a0f);
            scene.fog = new THREE.FogExp2(0x0a0a0f, 0.012);

            camera = new THREE.PerspectiveCamera(70, container.clientWidth / 600, 0.1, 1000);
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, 600);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            // 카메라 위치 설정
            camera.position.set(12, 10, 20);
            camera.lookAt(0, 0, -20);

            // 2. 조명
            var ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
            scene.add(ambientLight);
            var light = new THREE.PointLight(0xffd54f, 1.2, 50);
            light.position.set(0, 8, -10);
            scene.add(light);

            // 3. PLAXIS 스타일 3D 지반 유한요소 메쉬 (Ground Solid Elements)
            var groundGeo = new THREE.BoxGeometry(36, 26, 80);
            var groundMat = new THREE.MeshStandardMaterial({
                color: 0x2e2d2b,
                wireframe: true,
                transparent: true,
                opacity: 0.3
            });
            groundMesh = new THREE.Mesh(groundGeo, groundMat);
            groundMesh.position.set(0, 3, -20);
            scene.add(groundMesh);

            // 4. 터널 3D 굴착 공간
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
            var tunnelMesh = new THREE.Mesh(tunnelGeo, tunnelMat);
            tunnelMesh.position.set(0, 0, -60);
            scene.add(tunnelMesh);

            // 5. PLAXIS 3D 소성 파괴 컨투어 영역 (Yield Zone)
            var yieldGeo = new THREE.CylinderGeometry(R + 2.2, R + 2.2, 20, 16, 10, true, 0, Math.PI);
            var yieldMat = new THREE.MeshBasicMaterial({ color: 0xff1744, wireframe: true, transparent: true, opacity: 0.7 });
            yieldZoneMesh = new THREE.Mesh(yieldGeo, yieldMat);
            yieldZoneMesh.rotation.x = Math.PI / 2;
            yieldZoneMesh.position.set(0, 0, -20);
            scene.add(yieldZoneMesh);

            // 애니메이션 루프
            function animate() {
                requestAnimationFrame(animate);
                renderer.render(scene, camera);
            }
            animate();
        });

        // AI 에이전트 시뮬레이션 및 API 코드 실시간 스크립팅
        function runAiAgent() {
            var inputTxt = document.getElementById('aiInput').value;
            var chatBox = document.getElementById('chatBox');

            // 1. 유저 메시지 출력
            chatBox.innerHTML += '<div class="ai-msg user-msg">> User: ' + inputTxt + '</div>';

            // 2. AI 에이전트 PLAXIS API 코드 생성 프로세스 시뮬레이션
            setTimeout(function() {
                chatBox.innerHTML += '<div class="ai-msg agent-msg">[AI 에이전트] 자연어 해석 중... ➔ PLAXIS Scripting API 변환</div>';
                chatBox.innerHTML += '<div class="ai-msg plaxis-code">>>> plx.new()\n>>> g_o.borehole(0, 0)\n>>> g_o.mesh(3D_Solid)\n>>> g_o.calculate()</div>';
                chatBox.scrollTop = chatBox.scrollHeight;
            }, 600);

            // 3. 클라우드 렌더링 및 3D 파괴 영역 업데이트
            setTimeout(function() {
                // 3D 소성 파괴 컨투어 강조
                yieldZoneMesh.material.color.setHex(0xff1744);
                yieldZoneMesh.scale.set(1.3, 1.0, 1.3);

                chatBox.innerHTML += '<div class="ai-msg agent-msg">[AI 에이전트] 3D 수치해석 완료.</div>';
                chatBox.innerHTML += '<div class="ai-msg">------------------------------</div>';
                chatBox.innerHTML += '<div class="ai-msg">• STA 20~40m 3D FS: <b>0.92 (NG)</b></div>';
                chatBox.innerHTML += '<div class="ai-msg">• 파괴 형태: <b>상반 천단 소성 영역 확장</b></div>';
                chatBox.innerHTML += '<div class="status-badge">판정 결과: NG (강관다단 보강 필요)</div>';
                chatBox.scrollTop = chatBox.scrollHeight;
            }, 1500);
        }
    </script>
</body>
</html>
"""

# ======================================================================
# 3. Streamlit 대시보드 레이아웃
# ======================================================================
components.html(ai_plaxis_web_html, height=620)

st.divider()

# 하단 파이썬 제어 대시보드
col_ctrl1, col_ctrl2 = st.columns(2)

with col_ctrl1:
    st.subheader("⚙️ AI 에이전트 파라미터 제어")
    st.selectbox("AI 에이전트 연동 모델", ["OpenAI GPT-4o Agent", "Bentley iTwin AI Engine", "Claude 3.5 Sonnet"])
    st.slider("지반 불확실성 가중치 (Monte Carlo)", 0.0, 1.0, 0.15)

with col_ctrl2:
    st.subheader("📤 GTS NX / PLAXIS 클라우드 내보내기")
    if st.button("🚀 생성된 3D FEA 스크립트(.py / .mct) 내보내기"):
        st.success("AI 에이전트가 자동 작성한 PLAXIS Python API 및 GTS NX MCT 스크립트가 도출되었습니다!")
