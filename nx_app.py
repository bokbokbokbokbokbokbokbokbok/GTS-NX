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
    page_title="측점(Station) 타이핑 & DXF 업로드 3D 연동기",
    page_icon="📐",
    layout="wide"
)

st.title("📐 측점(Station) 타이핑 입력 & 측점별 DXF CAD 3D 연동기")
st.markdown("측점을 직접 텍스트로 입력하여 추가하고, 각 측점마다 개별 **DXF 도면**을 첨부하여 위성 지도 및 3D 해석 모델을 생성합니다.")

st.divider()

# ======================================================================
# 2. DXF CAD 파서
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
# 3. Leaflet 위성 지도 + Three.js 3D 로드뷰 연동 HTML/JS
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
            background: #00e
