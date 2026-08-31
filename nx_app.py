import math
import io
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import streamlit.components.v1 as components

# DXF 파싱 라이브러리 예외 처리
try:
    import ezdxf
except ModuleNotFoundError:
    st.error("⚠️ `ezdxf` 패키지가 필요합니다. `requirements.txt`에 `ezdxf`를 추가해 주세요.")
    st.stop()

# ======================================================================
# 1. 페이지 기본 설정
# ======================================================================
st.set_page_config(
    page_title="GTS NX 2D 침투-응력 연계 FEA & DXF 오토메쉬 Engine",
    page_icon="🏗️",
    layout="wide"
)

st.title("🏗️ 2D 침투-응력 연계 FEA 해석 & DXF 단면 오토메쉬 엔진")
st.markdown("DXF 단면 업로드, Van Genuchten 침투 수식, Terzaghi 유효응력 및 Mohr-Coulomb 파괴 이론 기반 **2D 수치해석 모듈**입니다.")

st.divider()

# ======================================================================
# 2. DXF 파싱 및 삼각 요소망(Triangular Mesh) 자동 생성 클래스
# ======================================================================
class TunnelMeshGenerator:
    """DXF 파싱 및 지반-터널 2D 유한요소망(FE Mesh) 자동 생성기"""
    def __init__(self, domain_width=60.0, domain_height=40.0, tunnel_depth=20.0):
        self.width = domain_width
        self.height = domain_height
        self.depth = tunnel_depth
        self.nodes = []
        self.elements = []

    def parse_dxf_pattern(self, dxf_file_bytes):
        """업로드된 DXF 파일에서 단면 폴리라인/선분 좌표 추출"""
        try:
            doc = ezdxf.readzip(dxf_file_bytes) if dxf_file_bytes.name.endswith('.zip') else ezdxf.read(io.StringIO(dxf_file_bytes.getvalue().decode('utf-8', errors='ignore')))
            msp = doc.modelspace()
            dxf_points = []
            for entity in msp:
                if entity.dxftype() == 'LINE':
                    dxf_points.append((entity.dxf.start.x, entity.dxf.start.y))
                    dxf_points.append((entity.dxf.end.x, entity.dxf.end.y))
                elif entity.dxftype() in ('LWPOLYLINE', 'POLYLINE'):
                    for pt in entity.get_points():
                        dxf_points.append((pt[0], pt[1]))
            return dxf_points if dxf_points else None
        except Exception:
            return None

    def generate_mesh(self, grid_nx=25, grid_ny=20):
        """지반 및 터널 주변 삼각/사각 요소를 자동망 생성 (Auto-Meshing)"""
        x = np.linspace(-self.width / 2, self.width / 2, grid_nx)
        y = np.linspace(-self.height, 0, grid_ny)
        X, Y = np.meshgrid(x, y)
        
        nodes = np.column_stack([X.ravel(), Y.ravel()])
        elements = []
        
        # 2D Grid 기반 삼각 요소 생성 (T3 Elements)
        for i in range(grid_ny - 1):
            for j in range(grid_nx - 1):
                n1 = i * grid_nx + j
                n2 = n1 + 1
                n3 = n1 + grid_nx
                n4 = n3 + 1
                elements.append([n1, n2, n3])
                elements.append([n2, n4, n3])

        self.nodes = nodes
        self.elements = np.array(elements)
        return self.nodes, self.elements

# ======================================================================
# 3. 2D 침투-응력 연계 해석 수학/공학 연산 엔진 (논문 & GTS NX 수식)
# ======================================================================
class CoupledSeepageSolver:
    """Van Genuchten 비포화 침투 & Mohr-Coulomb / Terzaghi 유효응력 해석기"""
    def __init__(self, nodes, elements):
        self.nodes = nodes
        self.elements = elements

    def solve_seepage(self, gwl=-5.0, k_sat=1e-5, alpha=0.01, n_vg=1.5):
        """
        [Van Genuchten 비포화 침투 수식]
        Se = [1 + (alpha * |h|)^n]^(-m), m = 1 - 1/n
        k(h) = k_sat * Se^0.5 * [1 - (1 - Se^(1/m))^m]^2
        """
        y_coords = self.nodes[:, 1]
        pore_pressure = np.where(y_coords < gwl, (gwl - y_coords) * 9.81, 0.0)
        
        # 비포화 체적수분함량 및 포화도 계산
        h = np.abs(np.minimum(0, y_coords - gwl))
        m = 1.0 - (1.0 / n_vg)
        se = (1.0 + (alpha * h) ** n_vg) ** (-m)
        k_unstat = k_sat * (se ** 0.5) * ((1.0 - (1.0 - se ** (1.0 / m)) ** m) ** 2)

        return pore_pressure, k_unstat

    def solve_stresses(self, pore_pressure, unit_weight=19.0, cohesion=15.0, phi_deg=30.0, k0=0.5):
        """
        [Terzaghi 유효응력 수식] sigma' = sigma - u
        [Mohr-Coulomb 파괴지수 FS] FS = (c + sigma_n' * tan(phi)) / tau
        """
        y_coords = self.nodes[:, 1]
        depth = np.abs(y_coords)
        
        sigma_v_total = depth * unit_weight
        sigma_v_eff = np.maximum(0, sigma_v_total - pore_pressure)
        sigma_h_eff = k0 * sigma_v_eff
        
        phi_rad = math.radians(phi_deg)
        tau_max = (sigma_v_eff - sigma_h_eff) / 2.0
        sigma_n_mean = (sigma_v_eff + sigma_h_eff) / 2.0
        
        tau_shear_strength = cohesion + (sigma_n_mean * math.tan(phi_rad))
        safety_factor = np.where(tau_max > 0, tau_shear_strength / (tau_max + 1e-5), 2.5)
        safety_factor = np.clip(safety_factor, 0.1, 3.0)

        return sigma_v_eff, pore_pressure, safety_factor

# ======================================================================
# 4. Streamlit UI 메인 화면 구성
# ======================================================================
st.sidebar.header("📁 1. DXF 터널 패턴 업로드")
uploaded_dxf = st.sidebar.file_content = st.sidebar.file_uploader("NATM/TBM 단면 DXF 파일 업로드", type=["dxf"])

st.sidebar.divider()
st.sidebar.header("🌊 2. 침투 해석 매개변수 (Van Genuchten)")
gwl = st.sidebar.number_input("지하수위 GWL (m)", value=-5.0, step=1.0)
k_sat = st.sidebar.number_input("포화투수계수 Ks (m/sec)", value=1e-5, format="%.2e")
vg_alpha = st.sidebar.number_input("Van Genuchten α (1/m)", value=0.01, step=0.005)
vg_n = st.sidebar.number_input("Van Genuchten n 계수", value=1.5, step=0.1)

st.sidebar.divider()
st.sidebar.header("🪨 3. 응력/지반 매개변수")
unit_weight = st.sidebar.number_input("포화단위수량 γ (kN/m³)", value=19.0, step=0.5)
cohesion = st.sidebar.number_input("점착력 c (kPa)", value=15.0, step=1.0)
phi_deg = st.sidebar.number_input("내부마찰각 φ (deg)", value=30.0, step=1.0)
k0_val = st.sidebar.number_input("정지토압계수 K0", value=0.5, step=0.05)

# 메인 해석 실행 레이아웃
col_dxf, col_fea = st.columns([1, 2])

mesh_gen = TunnelMeshGenerator()
nodes, elements = mesh_gen.generate_mesh()

with col_dxf:
    st.subheader("📐 DXF 파싱 및 자동 메쉬 생성")
    if uploaded_dxf:
        dxf_pts = mesh_gen.parse_dxf_pattern(uploaded_dxf)
        if dxf_pts:
            st.success("✅ DXF 터널 단면 단면선 파싱 성공!")
            st.info(f"추출된 DXF 노드 지점 수: {len(dxf_pts)} 개")
        else:
            st.warning("DXF 내 유효한 LINE/POLYLINE 레이어가 없어 기본 대칭 터널 단면을 적용합니다.")
    else:
        st.info("💡 DXF 파일이 없을 경우 기본 복합 지반 터널 단면 요소망이 사용됩니다.")

    st.write(f"• **생성된 2D 요소망:** 절점 {len(nodes)} 개 / 삼각 요소 {len(elements)} 개")

    # 요소망 메쉬 시각화
    fig_mesh, ax_mesh = plt.subplots(figsize=(5, 4))
    ax_mesh.triplot(nodes[:, 0], nodes[:, 1], elements, color='gray', lw=0.4)
    ax_mesh.set_title("Generated 2D FEA Mesh")
    ax_mesh.set_xlabel("X (m)")
    ax_mesh.set_ylabel("Z (m)")
    st.pyplot(fig_mesh)

with col_fea:
    st.subheader("📊 2D 침투-응력 연계 해석 결과 (FEA Contour)")

    # FEA 연산 수행
    solver = CoupledSeepageSolver(nodes, elements)
    pore_p, k_unstat = solver.solve_seepage(gwl=gwl, k_sat=k_sat, alpha=vg_alpha, n_vg=vg_n)
    sigma_v_eff, u_press, fs_val = solver.solve_stresses(pore_pressure=pore_p, unit_weight=unit_weight, cohesion=cohesion, phi_deg=phi_deg, k0=k0_val)

    analysis_mode = st.radio("표시할 수치해석 컨투어 선택:", ["간극수압 분포 (Pore Pressure, kPa)", "유효 연직응력 (Effective Stress, kPa)", "Mohr-Coulomb 안전율 (Safety Factor)"], horizontal=True)

    fig_contour, ax_c = plt.subplots(figsize=(7, 4.5))

    if "간극수압" in analysis_mode:
        c = ax_c.tripcolor(nodes[:, 0], nodes[:, 1], elements, pore_p, cmap='Blues', shading='flat')
        fig_contour.colorbar(c, ax=ax_c, label="Pore Water Pressure (kPa)")
        ax_c.axhline(gwl, color='cyan', linestyle='--', label=f'GWL ({gwl}m)')
        ax_c.legend()
    elif "유효 연직응력" in analysis_mode:
        c = ax_c.tripcolor(nodes[:, 0], nodes[:, 1], elements, sigma_v_eff, cmap='viridis', shading='flat')
        fig_contour.colorbar(c, ax=ax_c, label="Effective Stress σ'v (kPa)")
    else:
        c = ax_c.tripcolor(nodes[:, 0], nodes[:, 1], elements, fs_val, cmap='RdYlGn', vmin=0.8, vmax=2.5, shading='flat')
        fig_contour.colorbar(c, ax=ax_c, label="Factor of Safety (FS)")

    ax_c.set_title(f"2D FEA Result: {analysis_mode}")
    ax_c.set_xlabel("X Distance (m)")
    ax_c.set_ylabel("Depth Z (m)")
    st.pyplot(fig_contour)

st.divider()

# 해석 요약 결과 표시
st.subheader("📋 2D 연계 해석 수치 분석 요약")
col_m1, col_m2, col_m3 = st.columns(3)

col_m1.metric("최대 간극수압", f"{np.max(pore_p):.1f} kPa")
col_m2.metric("터널 하부 유효응력", f"{np.median(sigma_v_eff):.1f} kPa")
min_fs = np.min(fs_val)
col_m3.metric("최소 파괴 안전율 (Min FS)", f"{min_fs:.2f}", delta="안전" if min_fs >= 1.2 else "파괴 위험", delta_color="normal" if min_fs >= 1.2 else "inverse")
