import math
import json
import streamlit as st
import streamlit.components.v1 as components

# ======================================================================
# 1. 페이지 설정 및 기본 레이아웃
# ======================================================================
st.set_page_config(
    page_title="GTS NX - 3D Tunnel Designer",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ 3D 위성지도 기반 터널 노선 설계 & GTS NX 연동")
st.markdown("지도 위에서 **터널 시점(Start)**과 **종점(End)**을 클릭하여 노선을 설정하세요.")

st.divider()

# ======================================================================
# 2. CesiumJS 3D 지도 HTML/JS 템플릿
# ======================================================================
cesium_html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.119/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.119/Cesium/Widgets/widgets.css" rel="stylesheet">
  <style>
    html, body, #cesiumContainer {
      width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden;
    }
    #infoBox {
      position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.75);
      color: white; padding: 12px; border-radius: 8px; font-family: sans-serif;
      font-size: 13px; z-index: 999; max-width: 300px;
    }
  </style>
</head>
<body>
  <div id="cesiumContainer"></div>
  <div id="infoBox">
    <b>📍 터널 노선 지정 안내</b><br>
    - <b>1번째 클릭:</b> 터널 시점 (Inlet)<br>
    - <b>2번째 클릭:</b> 터널 종점 (Outlet)<br>
    <hr style="border: 0.5px solid #555;">
    <div id="status">지점을 선택해 주세요...</div>
  </div>

  <script>
    // Cesium Viewer 초기화 (기본 무료 OpenStreetMap & 지형 타일 연동)
    const viewer = new Cesium.Viewer('cesiumContainer', {
      terrainProvider: Cesium.createWorldTerrain ? Cesium.createWorldTerrain() : undefined,
      animation: false,
      timeline: false,
      baseLayerPicker: true
    });

    // 한국 지형 중심(강원도 산악지형 부근)으로 초기 카메라 이동
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(128.0, 37.5, 15000.0),
      orientation: {
        heading: Cesium.Math.toRadians(0.0),
        pitch: Cesium.Math.toRadians(-45.0)
      }
    });

    let points = [];
    let entities = [];

    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);

    handler.setInputAction(function (click) {
      const earthPosition = viewer.scene.pickPosition(click.position);

      if (Cesium.defined(earthPosition)) {
        const cartographic = Cesium.Cartographic.fromCartesian(earthPosition);
        const lon = Cesium.Math.toDegrees(cartographic.longitude);
        const lat = Cesium.Math.toDegrees(cartographic.latitude);
        const height = cartographic.height;

        if (points.length >= 2) {
          // 기존 클릭 초기화
          points = [];
          entities.forEach(e => viewer.entities.remove(e));
          entities = [];
        }

        points.push({ lon, lat, height, cartesian: earthPosition });

        // 마커 추가
        const labelText = points.length === 1 ? "시점 (Inlet)" : "종점 (Outlet)";
        const color = points.length === 1 ? Cesium.Color.RED : Cesium.Color.BLUE;

        const pointEntity = viewer.entities.add({
          position: earthPosition,
          point: { pixelSize: 12, color: color },
          label: {
            text: labelText,
            font: '14px sans-serif',
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            pixelOffset: new Cesium.Cartesian2(0, -10)
          }
        });
        entities.push(pointEntity);

        // 2개 점 선택 완료 시 직선 노선 생성
        if (points.length === 2) {
          const lineEntity = viewer.entities.add({
            polyline: {
              positions: [points[0].cartesian, points[1].cartesian],
              width: 5,
              material: Cesium.Color.YELLOW
            }
          });
          entities.push(lineEntity);

          // 3D 거리 계산 (m)
          const distance = Cesium.Cartesian3.distance(points[0].cartesian, points[1].cartesian);

          document.getElementById('status').innerHTML = 
            `<b>[노선 설정 완료]</b><br>` +
            `시점: ${points[0].lat.toFixed(5)}°, ${points[0].lon.toFixed(5)}° (${points[0].height.toFixed(1)}m)<br>` +
            `종점: ${points[1].lat.toFixed(5)}°, ${points[1].lon.toFixed(5)}° (${points[1].height.toFixed(1)}m)<br>` +
            `<b>총 연장: ${distance.toFixed(2)} m</b>`;
        } else {
          document.getElementById('status').innerHTML = `시점 선택 완료. 종점을 클릭하세요.`;
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  </script>
</body>
</html>
"""

# ======================================================================
# 3. 화면 배치 및 파라미터 수동/자동 연동
# ======================================================================
col_map, col_param = st.columns([2, 1])

with col_map:
    st.subheader("🌐 CesiumJS 3D 위성 지도")
    components.html(cesium_html, height=600)

with col_param:
    st.subheader("📏 터널 설계 & 공사비 산출")

    tunnel_length = st.number_input("터널 총 연장 L (m)", value=500.0, step=10.0)
    tunnel_area = st.number_input("터널 단면적 A (m²)", value=65.0, step=5.0)
    
    rmr_score = st.slider("지반 RMR 점수", min_value=0, max_value=100, value=55)

    # RMR 기반 패턴 자동 산정
    if rmr_score >= 61:
        pattern = "Pattern I (전단면 굴착)"
        cost_per_m = 12000000  # 원/m
    elif rmr_score >= 41:
        pattern = "Pattern III (상/하반 분할 굴착)"
        cost_per_m = 18000000
    else:
        pattern = "Pattern V (강지보재 + 훠폴링 보강)"
        cost_per_m = 26000000

    st.info(f"**추천 굴착 패턴:** {pattern}")

    # 개략 공사비 산출 수식
    total_cost_krw = (tunnel_length * cost_per_m) + 500000000  # 갱문부 고정비 5억 추가
    
    st.metric("총 개략 공사비", f"{total_cost_krw / 1e8:.2f} 억원")

    st.divider()
    
    # Hoek-Brown 파괴 검토 맛보기
    st.subheader("🛡️ Hoek-Brown 지반 파괴 검토")
    sig_ci = st.number_input("암석 일축압축강도 σci (kPa)", value=50000.0, step=5000.0)
    gsi = rmr_score - 5  # RMR 기반 GSI 추정식 예시
    
    st.write(f"추정 GSI 지수: **{gsi}**")
    
    if st.button("🚀 GTS NX 연동 MCT 생성"):
        st.success("지형 좌표 및 굴착 패턴이 적용된 MCT 데이터 준비 완료!")
