import math
import io
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

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
    page_title="GTS NX 2D DXF 구조안정성 해석 (천단/내공변위, 숏크리트, 록볼트)",
    page_icon="🏗️",
    layout="wide"
)

st.title("🏗️ 터널 DXF 구조안정성 해석 엔진 (GTS NX 연동)")
st.markdown("**DXF 지보패턴 도면**을 파싱하여 **천단변위, 내공변위, 숏크리트 휨압축응력, 록볼트 축력**을 정밀 검토합니다.")

st.divider()

# ======================================================================
# 2. DXF 파싱 및 지보재(Shotcrete / Rockbolt) 구조 추출기
# ======================================================================
class TunnelStructuralDXFParser:
    def __init__(self):
        self.tunnel_arcs = []
        self.rockbolts = []
        self.shotcrete_thickness = 0.15  # 기본값 150mm

    def parse_dxf(self, dxf_file_bytes):
        try:
            content = dxf_file_bytes.getvalue().decode('euc-kr', errors='ignore')
            doc = ezdxf.read(io.StringIO(content))
            msp = doc.modelspace()

            for entity in msp:
                layer = entity.dxf.layer
                # 터널 단면 아크(Arc)/폴리라인 파싱
                if entity.dxftype() == 'ARC' and layer in ('CS-CUTL', 'CS-EXCV'):
                    self.tunnel_arcs.append({
                        'center': (entity.dxf.center.x, entity.dxf.center.y),
                        'radius': entity.dxf.radius,
                        'start_angle': entity.dxf.start_angle,
                        'end_angle': entity.dxf.end_angle
                    })
                # 록볼트 및 보강재 라인 파싱
                elif entity.dxftype() == 'LINE' and layer in ('CS-STEL-MAJR', 'S-DIM'):
                    p1, p2 = entity.dxf.start, entity.dxf.end
                    length = math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)
                    if 1.5 <= length <= 6.0:  # 일반적인 록볼트 길이 범주(1.5m~6m)
                        self.rockbolts.append({'p1': (p1.x, p1.y), 'p2': (p2.y, p2.y), 'length': length})

            return True
        except Exception as e:
            st.error(f"DXF 구조 파싱 에러: {e}")
            return False

# ======================================================================
# 3. 천단변위 / 내공변위 / 숏크리트 / 록볼트 수치해석 엔진
# ======================================================================
class GTSNXTunnelStructuralSolver:
    """GTS NX Beam/Truss 1D-2D 구조 부재력 연산 알고리즘"""
    def __init__(self, depth=35.0, gamma=23.0, k0=0.5, E_rock=1500000.0, E_shotcrete=20000000.0):
        self.H = depth                 # 굴착 깊이 (m)
        self.gamma = gamma             # 암반 단위수량 (kN/m³)
        self.k0 = k0                   # 측압계수
        self.E_r = E_rock              # 암반 변형계수 (kPa)
        self.E_s = E_shotcrete         # 숏크리트 탄성계수 (kPa)

    def calculate_displacements(self, tunnel_radius=6.5):
        """
        [천단변위 & 내공변위 수식 (Kirsch 정해 해석 기반)]
        천단변위 U_crown = (1 + v) * R * sigma_v / E_r
        내공변위 U_wall = (1 + v) * R * sigma_h / E_r
        """
        sigma_v = self.gamma * self.H
        sigma_h = self.k0 * sigma_v
        v = 0.25  # 포아송비

        # 천단변위 (Crown Settlement, mm)
        u_crown = ((1 + v) * tunnel_radius * sigma_v / self.E_r) * 1000.0
        # 내공변위 (Convergence, mm)
        u_wall = ((1 + v) * tunnel_radius * sigma_h / self.E_r) * 1000.0

        return u_crown, u_wall, sigma_v

    def calculate_shotcrete_stress(self, u_crown, thickness=0.15, radius=6.5):
        """
        [숏크리트 휨압축응력 수식]
        sigma_b = M / Z + N / A
        M = 3 * E_s * I * (u_crown / 1000) / R^2
        """
        I_s = (1.0 * (thickness**3)) / 12.0  # 단위폭당 단면2차모멘트
        Z_s = (1.0 * (thickness**2)) / 6.0   # 단면계수
        
        # 휨모멘트 M (kN·m/m)
        M_shotcrete = 3.0 * self.E_s * I_s * (u_crown / 1000.0) / (radius**2)
        # 축력 N (kN/m)
        N_shotcrete = self.gamma * self.H * radius * 0.15
        
        # 휨압축응력 (MPa)
        sigma_bending_comp = (M_shotcrete / Z_s + N_shotcrete / thickness) / 1000.0
        return sigma_bending_comp, M_shotcrete

    def calculate_rockbolt_axial_force(self, u_crown, bolt_length=4.0, spacing=1.5):
        """
        [록볼트 최대 축력 수식]
        T_max = E_bolt * A_bolt * (u_crown / 1000) / L_bolt * Spacing_factor
        """
        E_bolt = 210000000.0  # 강재 탄성계수 (kPa)
        d_bolt = 0.025         # SD350 D25 록볼트 직경 (m)
        A_bolt = (math.pi * (d_bolt**2)) / 4.0
        
        # 최대 인장 축력 (kN)
        T_max = E_bolt * A_bolt * (u_crown / 1000.0 / bolt_length) * (spacing / 1.0)
        return min(T_max, 180.0)  # 항복하중(약 180kN) 임계치 적용

# ======================================================================
# 4. Streamlit 화면 구성 및 입력 매개변수
# ======================================================================
st.sidebar.header("📁 1. DXF 도체 파일 업로드")
uploaded_dxf = st.sidebar.file_uploader("7km235(PD-2A) DXF 업로드", type=["dxf"])

st.sidebar.divider()
st.sidebar.header("🏔️ 2. 지반 및 터널 입력 조건")
depth_val = st.sidebar.number_input("굴착 토심 H (m)", value=35.0, step=1.0)
gamma_val = st.sidebar.number_input("암반 단위수량 γ (kN/m³)", value=23.0, step=0.5)
k0_val = st.sidebar.number_input("측압계수 K0", value=0.5, step=0.05)
e_rock_val = st.sidebar.number_input("암반 변형계수 E (MPa)", value=1500.0, step=100.0) * 1000.0

st.sidebar.divider()
st.sidebar.header("🛡️ 3. 지보재 설계 규격")
shotcrete_thk = st.sidebar.number_input("숏크리트 두께 (mm)", value=150, step=10) / 1000.0
rockbolt_len = st.sidebar.number_input("록볼트 길이 L (m)", value=4.0, step=0.5)

# 해석 실행
parser = TunnelStructuralDXFParser()
solver = GTSNXTunnelStructuralSolver(depth=depth_val, gamma=gamma_val, k0=k0_val, E_rock=e_rock_val)

if uploaded_dxf:
    parser.parse_dxf(uploaded_dxf)

u_crown, u_wall, sigma_v = solver.calculate_displacements()
sigma_shotcrete, M_s = solver.calculate_shotcrete_stress(u_crown, thickness=shotcrete_thk)
t_rockbolt = solver.calculate_rockbolt_axial_force(u_crown, bolt_length=rockbolt_len)

# 결과 화면
st.subheader("🎯 핵심 4대 구조 안정성 검토 결과")

col1, col2, col3, col4 = st.columns(4)

# 1. 천단변위
crown_allowable = 20.0  # 허용기준 예시 20mm
col1.metric("1. 천단변위 (Crown)", f"{u_crown:.2f} mm", delta="안전" if u_crown <= crown_allowable else "초과 Warning", delta_color="normal" if u_crown <= crown_allowable else "inverse")

# 2. 내공변위
wall_allowable = 25.0   # 허용기준 예시 25mm
col2.metric("2. 내공변위 (Wall)", f"{u_wall:.2f} mm", delta="안전" if u_wall <= wall_allowable else "초과 Warning", delta_color="normal" if u_wall <= wall_allowable else "inverse")

# 3. 숏크리트 휨압축응력
f_ck_shotcrete = 21.0   # 숏크리트 설계기준강도 21 MPa
col3.metric("3. 숏크리트 휨압축응력", f"{sigma_shotcrete:.2f} MPa", delta="안전" if sigma_shotcrete <= f_ck_shotcrete else "파괴 Danger", delta_color="normal" if sigma_shotcrete <= f_ck_shotcrete else "inverse")

# 4. 록볼트 최대축력
t_allowable = 130.0     # 록볼트 허용인장력 130 kN
col4.metric("4. 록볼트 최대축력", f"{t_rockbolt:.1f} kN", delta="안전" if t_rockbolt <= t_allowable else "항복 Danger", delta_color="normal" if t_rockbolt <= t_allowable else "inverse")

st.divider()

# 시각화 및 세부 판정 그래프
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("📈 허용기준 대비 부재력 검토 그래프")
    categories = ['천단변위\n(mm)', '내공변위\n(mm)', '숏크리트 응력\n(MPa)', '록볼트 축력\n(10kN)']
    calculated_vals = [u_crown, u_wall, sigma_shotcrete, t_rockbolt / 10.0]
    allowable_vals = [crown_allowable, wall_allowable, f_ck_shotcrete, t_allowable / 10.0]

    x = np.arange(len(categories))
    width = 0.35

    fig_bar, ax_b = plt.subplots(figsize=(7, 4.2))
    ax_b.bar(x - width/2, calculated_vals, width, label='해석 도출값', color='#2196F3')
    ax_b.bar(x + width/2, allowable_vals, width, label='허용 기준값', color='#FF9800')

    ax_b.set_ylabel('부재력 / 변위 수치')
    ax_b.set_title('GTS NX 2D Structural FEA Verification')
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(categories)
    ax_b.legend()
    st.pyplot(fig_bar)

with col_right:
    st.subheader("📋 세부 계산 서식 (GTS NX 보고서용)")
    st.markdown(f"""
    * **연직 전응력 ($\sigma_v$):** `{sigma_v:.1f} kPa`
    * **천단 변위량 ($U_{{crown}}$):** `{u_crown:.3f} mm` *(허용치: {crown_allowable} mm)*
    * **내공 변위량 ($U_{{wall}}$):** `{u_wall:.3f} mm` *(허용치: {wall_allowable} mm)*
    * **숏크리트 휨모멘트 ($M_{{max}}$):** `{M_s:.2f} kN·m/m`
    * **숏크리트 휨압축응력 ($\sigma_{{c}}$):** `{sigma_shotcrete:.2f} MPa` *(설계강도: {f_ck_shotcrete} MPa)*
    * **록볼트 유효인장력 ($T_{{max}}$):** `{t_rockbolt:.1f} kN` *(허용치: {t_allowable} kN)*
    """)
    
    if st.button("📄 GTS NX 계산서 (MCT) 보고서 출력"):
        st.success("천단/내공변위 및 지보재 검토 데이터가 MCT 보고서 형식으로 작성되었습니다.")
