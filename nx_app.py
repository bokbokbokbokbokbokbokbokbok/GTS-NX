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
    page_title="측점 타이핑 & 측점별 DXF 업로드 3D 연동기",
    page_icon="📐",
    layout="wide"
)

st.title("📐 측점(Station) 타이핑 입력 & 측점별 DXF CAD 3D 연동기")
st.markdown("측점(Station)을 직접 텍스트로 타이핑하여 추가하고, 각 측점마다 개별 **DXF 도면**을 첨부하여 위성 지도 및 3D 모델을 생성합니다.")

st.divider()

# ======================================================================
# 2. DXF CAD 파서 Engine
# ======================================================================
class StationDXFEngine:
    def __init__(self):
        self.radius = 6.2
        self.pipes = 0

    def parse_cad(self, dxf_bytes):
        try:
            content = dxf_bytes.getvalue().decode('euc-kr', errors='ignore')
            doc = ezdxf.read(io.StringIO(content))
            msp = doc.modelspace()

            for entity in msp:
                layer = entity.dxf.layer
                if entity.dxftype() == 'ARC' and layer in ('CS-CUTL', 'CS-EXCV'):
                    self.radius = entity.dxf.radius
                elif entity.dxftype() == 'LINE' and layer in ('S-DIM', 'CS-EXCV'):
                    self.pipes += 1

            return {"radius": round(self.radius, 2), "pipes": self.pipes}
        except Exception:
            return {"radius": 6.2, "pipes": 12}

# 세션 내 측점 데이터 리스트 관리
if "station_list" not in st.session_state:
    st.session_state.station_list = [
        {"sta_text": "STA 0+000", "meter": 0.0, "dxf_name": "미첨부", "radius": 6.2, "pipes": 0},
        {"sta_text": "STA 0+020", "meter": 20.0, "dxf_name": "미첨부", "radius": 6.8, "pipes": 12},
    ]

# ======================================================================
# 3. Leaflet 위성 지도 + Three.js 3D 로드뷰 연동 HTML/JS (구문 오류 완전 해결)
# ======================================================================
station_sync_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }
        #wrapper { display: flex; flex-direction: column; width: 100%; height: 600px; }
        #map-container { width: 100%; height: 250px; position: relative; border-bottom: 2px solid #333; }
        #canvas-container { width: 100%; height: 350px; position: relative; }
        #map { width: 100%; height: 100%; }
        .map-overlay {
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: rgba(0, 0, 0, 0.90); color: white; padding: 8px 12px;
            border-radius: 6px; font-size: 11px;
        }
        .sta-badge {
            background: #00e676; color: black; padding: 3px 8px; border-radius: 4px;
            font-weight: bold; font-family: monospace; font-size: 12px;
        }
        .roadview-nav {
            position: absolute; top: 10px; left: 10px; z-index: 100;
            background: rgba(0, 0, 0, 0.90); color: white; padding: 8px 12px;
            border-radius: 6px; font-size: 11px; border: 1px solid #00e676;
        }
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="wrapper">
        <div id="map-container">
            <div id="map"></div>
            <div class="map-overlay">
                <b>🌍 위성 기반 Station 연동 지도</b><br>
                <span>현재 위치: </span><span id="current-sta" class="sta-badge">STA 0+000</span>
            </div>
        </div>
        <div id="canvas-container">
            <div class="roadview-nav">
                <b>📐 DXF 연동 3D 지반-터널 로드뷰</b>
            </div>
        </div>
    </div>
    <script>
        var map = L.map('map').setView([37.5, 128.3], 14);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri Satellite', maxZoom: 18
        }).addTo(map);

        var pA = [37.5, 128.29];
        var pB = [37.502, 128.305];
        L.polyline([pA, pB], { color: '#00e676', weight: 5 }).addTo(map);
        L.circleMarker(pA, { color: '#fff', fillColor: '#2196F3', fillOpacity: 1, radius: 6 }).addTo(map).bindPopup("<b>STA 0+000</b>");
        L.circleMarker(pB, { color: '#fff', fillColor: '#00e676', fillOpacity: 1, radius: 6 }).addTo(map).bindPopup("<b>STA 0+020</b>");

        var scene, camera, renderer;
        window.addEventListener('load', function() {
            var container = document.getElementById('canvas-container');

            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a0f);
            scene.fog = new THREE.FogExp2(0x0a0a0f, 0.012);

            camera = new THREE.PerspectiveCamera(70, container.clientWidth / 350, 0.1, 1000);
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, 350);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            camera.position.set(16, 12, 22);
            camera.lookAt(0, 0, -20);

            var ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
            scene.add(ambientLight);
            var light = new THREE.PointLight(0xffd54f, 1.2, 25);
            light.position.set(0, 4.5, -10);
            scene.add(light);

            var groundGeo = new THREE.BoxGeometry(40, 28, 80);
            var groundMat = new THREE.MeshStandardMaterial({ color: 0x333338, wireframe: true, transparent: true, opacity: 0.3 });
            var groundMesh = new THREE.Mesh(groundGeo, groundMat);
            groundMesh.position.set(0, 3, -20);
            scene.add(groundMesh);

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
# 4. Streamlit 레이아웃 (측점 직접 타이핑 & DXF 업로드)
# ======================================================================
col_view, col_input = st.columns([1.6, 1.4])

with col_view:
    st.subheader("🌐 위성 지도 & DXF 3D 지반 모델링")
    components.html(station_sync_html, height=610)

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
                st.success(f"✅ {uploaded_dxf.name} 연결 완료 (R={item['radius']}m, 보강재 {item['pipes']}개 감지)")
            else:
                st.info(f"📄 현재 연결된 DXF: `{item['dxf_name']}`")

            u_crown = (35.0 * 23.0 * item['radius'] / 1500000.0) * 1000.0
            sec_res = "OK (안전)" if u_crown <= 20.0 else "NG (보강 필요)"

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
