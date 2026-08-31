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
    page_title="측점 타이핑 & DXF 3D 실시간 렌더링 연동기",
    page_icon="📐",
    layout="wide"
)

st.title("📐 측점(Station) 타이핑 입력 & 측점별 DXF CAD 3D 연동기")
st.markdown("측점(Station)별로 DXF 도면을 첨부하면 **3D 터널 형상과 강관 보강재가 실시간으로 반영**됩니다.")

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

            pipe_cnt = 0
            rad_val = 6.2

            for entity in msp:
                layer = entity.dxf.layer
                if entity.dxftype() == 'ARC' and layer in ('CS-CUTL', 'CS-EXCV'):
                    rad_val = entity.dxf.radius
                elif entity.dxftype() in ('LINE', 'CIRCLE') and layer in ('S-DIM', 'CS-EXCV', '0'):
                    pipe_cnt += 1

            # 최소 보강재 수 보정
            if pipe_cnt == 0:
                pipe_cnt = 12

            return {"radius": round(rad_val, 2), "pipes": pipe_cnt}
        except Exception:
            return {"radius": 6.2, "pipes": 12}

# 세션 내 측점 데이터 리스트 관리
if "station_list" not in st.session_state:
    st.session_state.station_list = [
        {"sta_text": "STA 0+000", "meter": 0.0, "dxf_name": "10km210.dxf", "radius": 6.2, "pipes": 12},
        {"sta_text": "STA 0+020", "meter": 20.0, "dxf_name": "미첨부", "radius": 6.8, "pipes": 8},
    ]

# 선택된 현재 대표 파라미터 도출 (첫 번째 측점 기준)
active_radius = st.session_state.station_list[0]['radius']
active_pipes = st.session_state.station_list[0]['pipes']

# ======================================================================
# 3. Leaflet 위성 지도 + Three.js 3D 동적 연동 HTML/JS (f-string 적용)
# ======================================================================
station_sync_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; background-color: #0b0b10; font-family: sans-serif; }}
        #wrapper {{ display: flex; flex-direction: column; width: 100%; height: 600px; }}
        #map-container {{ width: 100%; height: 230px; position: relative; border-bottom:
