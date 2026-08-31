import json
import math
from typing import Dict, List, Any, Optional


class GTSNXDataConverter:
    """
    웹앱 사용자 입력을 GTS NX API용 JSON 및 .MCT 파일 포맷으로 변환하는 모듈
    """

    def __init__(self, project_name: str = "GTS_NX_Automated_Model"):
        self.project_name = project_name
        self.materials: List[Dict[str, Any]] = []
        self.nodes: List[Dict[str, Any]] = []
        self.elements: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1. 지반 및 구조 재료(Material) 데이터 추가
    # ------------------------------------------------------------------
    def add_material_mohr_coulomb(
        self,
        mat_id: int,
        name: str,
        e_modulus: float,      # elastic modulus (kPa)
        poisson_ratio: float,  # nu
        unit_weight: float,    # gamma (kN/m3)
        cohesion: float,       # c (kPa)
        friction_angle: float  # phi (deg)
    ):
        """Mohr-Coulomb 모델 재료 정의"""
        mat_data = {
            "id": mat_id,
            "name": name,
            "type": "MOHR-COULOMB",
            "elastic_modulus": e_modulus,
            "poisson_ratio": poisson_ratio,
            "unit_weight": unit_weight,
            "cohesion": cohesion,
            "friction_angle": friction_angle
        }
        self.materials.append(mat_data)

    def add_material_hoeke_brown(
        self,
        mat_id: int,
        name: str,
        e_modulus: float,
        poisson_ratio: float,
        unit_weight: float,
        sig_ci: float,         # 일축압축강도 (kPa)
        gsi: float,            # GSI 지수
        mi: float,             # 암종 파라미터
        dist_factor: float = 0 # 교란도 D (0~1)
    ):
        """Hoek-Brown 암반 모델 재료 정의"""
        mat_data = {
            "id": mat_id,
            "name": name,
            "type": "HOEK-BROWN",
            "elastic_modulus": e_modulus,
            "poisson_ratio": poisson_ratio,
            "unit_weight": unit_weight,
            "sig_ci": sig_ci,
            "gsi": gsi,
            "mi": mi,
            "dist_factor": dist_factor
        }
        self.materials.append(mat_data)

    # ------------------------------------------------------------------
    # 2. 절점(Node) 및 요소(Element) 데이터 추가
    # ------------------------------------------------------------------
    def add_node(self, node_id: int, x: float, y: float, z: float):
        """3D/2D 절점 좌표 정의"""
        self.nodes.append({"id": node_id, "x": x, "y": y, "z": z})

    def add_element(self, elem_id: int, elem_type: str, mat_id: int, node_ids: List[int]):
        """요소(메쉬) 정의 (예: 2D Plane Strain / 3D Solid)"""
        self.elements.append({
            "id": elem_id,
            "type": elem_type,
            "mat_id": mat_id,
            "nodes": node_ids
        })

    # ------------------------------------------------------------------
    # 3. GTS NX Open API (JSON) 규격으로 변환
    # ------------------------------------------------------------------
    def to_api_json(self) -> str:
        """MIDAS GTS NX RESTful API 통신용 JSON 포맷 생성"""
        api_payload = {
            "header": {
                "project": self.project_name,
                "version": "2026.1",
                "unit": {"length": "M", "force": "KN"}
            },
            "materials": self.materials,
            "nodes": self.nodes,
            "elements": self.elements
        }
        return json.dumps(api_payload, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 4. GTS NX 파일 드래그앤드롭용 .MCT 텍스트 생성
    # ------------------------------------------------------------------
    def to_mct_format(self) -> str:
        """GTS NX 전용 MCT(Midas C&T) 텍스트 파일 내용 생성"""
        mct_lines = []
        
        # 파일 헤더
        mct_lines.append(f"*UNIT\n  M, KN, C, SEC\n")
        
        # 재료 섹션 (*MATERIAL)
        mct_lines.append("*MATERIAL")
        for mat in self.materials:
            mct_lines.append(f"; Material Name: {mat['name']}")
            if mat['type'] == 'MOHR-COULOMB':
                # MCT 고유 포맷 라인 작성
                mct_lines.append(
                    f"  {mat['id']}, ISOTROPIC, {mat['elastic_modulus']}, {mat['poisson_ratio']}, "
                    f"{mat['unit_weight']}, MOHR-COULOMB, {mat['cohesion']}, {mat['friction_angle']}"
                )
            elif mat['type'] == 'HOEK-BROWN':
                mct_lines.append(
                    f"  {mat['id']}, ISOTROPIC, {mat['elastic_modulus']}, {mat['poisson_ratio']}, "
                    f"{mat['unit_weight']}, HOEK-BROWN, {mat['sig_ci']}, {mat['gsi']}, {mat['mi']}"
                )
        mct_lines.append("")

        # 절점 섹션 (*NODE)
        if self.nodes:
            mct_lines.append("*NODE")
            for n in self.nodes:
                mct_lines.append(f"  {n['id']}, {n['x']}, {n['y']}, {n['z']}")
            mct_lines.append("")

        # 요소 섹션 (*ELEMENT)
        if self.elements:
            mct_lines.append("*ELEMENT")
            for e in self.elements:
                node_str = ", ".join(map(str, e['nodes']))
                mct_lines.append(f"  {e['id']}, {e['type']}, {e['mat_id']}, {node_str}")
            mct_lines.append("")

        mct_lines.append("*END")
        return "\n".join(mct_lines)

    # ------------------------------------------------------------------
    # 5. 기존 MCT 파일 내용 읽기/파싱 (Reverse Parsing)
    # ------------------------------------------------------------------
    @classmethod
    from_mct_text(cls, mct_content: str):
        """업로드된 .mct 파일 텍스트를 파싱하여 객체로 복원"""
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

            # 파싱 섹션별 처리 (단순화 예시)
            if current_section == "*NODE":
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    converter.add_node(
                        node_id=int(parts[0]),
                        x=float(parts[1]),
                        y=float(parts[2]),
                        z=float(parts[3])
                    )

        return converter


# ======================================================================
# 사용 예시 (웹앱 FastAPI / Flask 연동 코드 형태)
# ======================================================================
if __name__ == "__main__":
    # 1. 객체 생성
    gts_model = GTSNXDataConverter(project_name="Tunnel_Section_Analysis")

    # 2. 웹 UI에서 사용자가 입력한 데이터 적용 (예: 토사 및 암반 지반)
    gts_model.add_material_mohr_coulomb(
        mat_id=1, name="Soft Soil Layer",
        e_modulus=25000.0, poisson_ratio=0.33, unit_weight=18.5,
        cohesion=12.0, friction_angle=26.0
    )

    gts_model.add_material_hoeke_brown(
        mat_id=2, name="Weathered Rock",
        e_modulus=850000.0, poisson_ratio=0.25, unit_weight=24.0,
        sig_ci=45000.0, gsi=55.0, mi=12.0, dist_factor=0.0
    )

    # 3. 절점 좌표 입력 (단순 예시)
    gts_model.add_node(node_id=1, x=0.0, y=0.0, z=0.0)
    gts_model.add_node(node_id=2, x=10.0, y=0.0, z=0.0)

    # 4. API 전달용 JSON 출력 확인
    json_output = gts_model.to_api_json()
    print("=== [GTS NX API JSON Output] ===")
    print(json_output[:350] + "...\n")

    # 5. GTS NX 파일 연동용 MCT 출력 확인
    mct_output = gts_model.to_mct_format()
    print("=== [GTS NX MCT Text Format Output] ===")
    print(mct_output)
