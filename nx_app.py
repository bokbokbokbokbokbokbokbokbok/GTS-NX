import json
import math
import streamlit as st
from typing import Dict, List, Any


# ======================================================================
# 1. GTS NX 데이터 변환 엔진 클래스
# ======================================================================
class GTSNXDataConverter:
    """웹앱 사용자 입력을 GTS NX API용 JSON 및 .MCT 파일 포맷으로 변환하는 모듈"""

    def __init__(self, project_name: str = "GTS_NX_Automated_Model"):
        self.project_name = project_name
        self.materials: List[Dict[str, Any]] = []
        self.nodes: List[Dict[str, Any]] = []
        self.elements: List[Dict[str, Any]] = []

    def add_material_mohr_coulomb(
        self,
        mat_id: int,
        name: str,
        e_modulus: float,
        poisson_ratio: float,
        unit_weight: float,
        cohesion: float,
        friction_angle: float,
    ):
        """Mohr-Coulomb 모델 재료 정의"""
        self.materials.append({
            "id": mat_id,
            "name": name,
            "type": "MOHR-COULOMB",
            "elastic_modulus": e_modulus,
            "poisson_ratio": poisson_ratio,
            "unit_weight": unit_weight,
            "cohesion": cohesion,
            "friction_angle": friction_angle,
        })

    def add_material_hoek_brown(
        self,
        mat_id: int,
        name: str,
        e_modulus: float,
        poisson_ratio: float,
        unit_weight: float,
        sig_ci: float,
        gsi: float,
        mi: float,
        dist_factor: float = 0.0,
    ):
        """Hoek-Brown 암반 모델 재료 정의"""
        self.materials.append({
            "id": mat_id,
            "name": name,
            "type": "HOEK-BROWN",
            "elastic_modulus": e_modulus,
            "poisson_ratio": poisson_ratio,
            "unit_weight": unit_weight,
            "sig_ci": sig_ci,
            "gsi": gsi,
            "mi": mi,
            "dist_factor": dist_factor,
        })

    def add_node(self, node_id: int, x: float, y: float, z: float):
        """3D/2D 절점 좌표 정의"""
        self.nodes.append({"id": node_id, "x": x, "y": y, "z": z})

    def add_element(
        self, elem_id: int, elem_type: str, mat_id: int, node_ids: List[int]
    ):
        """요소(메쉬) 정의"""
        self.elements.append({
            "id": elem_id,
            "type": elem_type,
            "mat_id": mat_id,
            "nodes": node_ids,
        })

    def to_api_json(self) -> str:
        """GTS NX RESTful API 연동용 JSON 포맷 생성"""
        api_payload = {
            "header": {
                "project": self.project_name,
                "version": "2026.1",
                "unit": {"length": "M", "force": "KN"},
            },
            "materials": self.materials,
            "nodes": self.nodes,
            "elements": self.elements,
        }
        return json.dumps(api_payload, indent=2, ensure_ascii=False)

    def to_mct_format(self) -> str:
        """GTS NX 드래그앤드롭용 .MCT 파일 포맷 생성"""
        mct_lines = []
        mct_lines.append("*UNIT\n  M, KN, C, SEC\n")

        # 재료 정의
        mct_lines.append("*MATERIAL")
        for mat in self.materials:
            mct_lines.append(f"; Material Name: {mat['name']}")
            if mat["type"] == "MOHR-COULOMB":
                mct_lines.append(
                    f"  {mat['id']}, ISOTROPIC, {mat['elastic_modulus']}, {mat['poisson_ratio']}, "
                    f"{mat['unit_weight']}, MOHR-COULOMB, {mat['cohesion']}, {mat['friction_angle']}"
                )
            elif mat["type"] == "HOEK-BROWN":
                mct_lines.append(
                    f"  {mat['id']}, ISOTROPIC, {mat['elastic_modulus']}, {mat['poisson_ratio']}, "
                    f"{mat['unit_weight']}, HOEK-BROWN, {mat['sig_ci']}, {mat['gsi']}, {mat['mi']}"
                )
        mct_lines.append("")

        # 절점 정의
        if self.nodes:
            mct_lines.append("*NODE")
            for n in self.nodes:
                mct_lines.append(f"  {n['id']}, {n['x']}, {n['y']}, {n['z']}")
            mct_lines.append("")

        # 요소 정의
        if self.elements:
            mct_lines.append("*ELEMENT")
            for e in self.elements:
                node_str = ", ".join(map(str, e["nodes"]))
                mct_lines.append(
                    f"  {e['id']}, {e['type']}, {e['mat_id']}, {node_str}"
                )
            mct_lines.append("")

        mct_lines.append("*END")
        return "\n".join(mct_lines)

    @classmethod
    def from_mct_text(cls, mct_content: str):
        """MCT 텍스트 파일 파싱 모듈"""
        converter = cls(project_name="Parsed_MCT_Project")
        lines = mct_content.splitlines()
        current_section = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith(";"):
                continue

            if line.startswith("*"):
                current_section = line.split()[0].upper()
                continue

            if current_section == "*NODE":
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    converter.add_node(
                        node_id=int(parts[0]),
                        x=float(parts[1]),
                        y=float(parts[2]),
                        z=float(parts[3]),
                    )

        return converter


# ======================================================================
# 2. Streamlit 웹앱 UI (User Interface)
# ======================================================================
st.set_page_config(
    page_title="GTS NX Data Automation", page_icon="🏗️", layout="wide"
)

st.title("🏗️ MIDAS GTS NX 데이터 변환 & 파싱 도구")
st.markdown(
    "지반 해석 매개변수를 입력받아 **GTS NX Open API (JSON)** 및 **.MCT 파일**로 자동 생성합니다."
)

st.divider()

# 좌측 입력 사이드바
st.sidebar.header("⚙️ 기본 설정")
project_name = st.sidebar.text_input("프로젝트 이름", "Tunnel_Section_Analysis")

# 기본 컨버터 객체 생성
converter = GTSNXDataConverter(project_name=project_name)

# 탭 구성 (입력 / 결과)
tab1, tab2 = st.tabs(["📝 지반 및 절점 정보 입력", "🚀 GTS NX 데이터 도출"])

with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Mohr-Coulomb 지반 재료 입력")
        mc_name = st.text_input("지층명 (MC)", "Soft Soil Layer")
        mc_e = st.number_input(
            "탄성계수 E (kPa)", value=25000.0, step=1000.0
        )
        mc_nu = st.number_input(
            "포아송비 ν", value=0.33, min_value=0.0, max_value=0.49
        )
        mc_gamma = st.number_input(
            "단위수량 γ (kN/m³)", value=18.5, step=0.5
        )
        mc_c = st.number_input("점착력 c (kPa)", value=12.0, step=1.0)
        mc_phi = st.number_input(
            "내부마찰각 φ (deg)", value=26.0, step=1.0
        )

        converter.add_material_mohr_coulomb(
            mat_id=1,
            name=mc_name,
            e_modulus=mc_e,
            poisson_ratio=mc_nu,
            unit_weight=mc_gamma,
            cohesion=mc_c,
            friction_angle=mc_phi,
        )

    with col2:
        st.subheader("2. Hoek-Brown 암반 재료 입력")
        hb_name = st.text_input("암반명 (HB)", "Weathered Rock")
        hb_e = st.number_input(
            "탄성계수 E (kPa)", value=850000.0, step=50000.0
        )
        hb_nu = st.number_input(
            "포아송비 ν (HB)", value=0.25, min_value=0.0, max_value=0.49
        )
        hb_gamma = st.number_input(
            "단위수량 γ (kN/m³) (HB)", value=24.0, step=0.5
        )
        hb_sig_ci = st.number_input(
            "일축압축강도 σci (kPa)", value=45000.0, step=1000.0
        )
        hb_gsi = st.number_input(
            "GSI 지수", value=55.0, min_value=0.0, max_value=100.0
        )
        hb_mi = st.number_input("암종 파라미터 mi", value=12.0, step=1.0)

        converter.add_material_hoek_brown(
            mat_id=2,
            name=hb_name,
            e_modulus=hb_e,
            poisson_ratio=hb_nu,
            unit_weight=hb_gamma,
            sig_ci=hb_sig_ci,
            gsi=hb_gsi,
            mi=hb_mi,
        )

    st.divider()

    st.subheader("3. 기본 샘플 절점 좌표 (Node)")
    # 기본 샘플 좌표 생성
    converter.add_node(1, 0.0, 0.0, 0.0)
    converter.add_node(2, 10.0, 0.0, 0.0)
    st.info(
        "기본 샘플 절점 (Node 1: [0,0,0], Node 2: [10,0,0])이 자동으로 세팅되었습니다."
    )

with tab2:
    st.header("📄 생성 결과 확인 및 다운로드")

    out_tab1, out_tab2 = st.tabs(
        ["💾 GTS NX .MCT 파일 포맷", "🔌 API 통신용 JSON 포맷"]
    )

    mct_text = converter.to_mct_format()
    json_text = converter.to_api_json()

    with out_tab1:
        st.code(mct_text, language="text")
        st.download_button(
            label="📥 .MCT 파일 다운로드",
            data=mct_text,
            file_name=f"{project_name}.mct",
            mime="text/plain",
        )

    with out_tab2:
        st.code(json_text, language="json")
        st.download_button(
            label="📥 API JSON 파일 다운로드",
            data=json_text,
            file_name=f"{project_name}.json",
            mime="application/json",
        )
