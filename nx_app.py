import os
import platform
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
import pandas as pd
import streamlit as st

# ==========================================
# 1. 한글 폰트 설정 (서버 및 로컬 환경 대응)
# ==========================================
if platform.system() == "Windows":
  rc("font", family="Malgun Gothic")
elif platform.system() == "Darwin":  # macOS
  rc("font", family="AppleGothic")
else:  # Linux (서버 배포 환경)
  font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
  if os.path.exists(font_path):
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    rc("font", family=font_name)
  else:
    plt.rcParams["font.family"] = "sans-serif"

# 그래프 마이너스 기호 깨짐 방지
plt.rcParams["axes.unicode_minus"] = False

# ==========================================
# 2. Streamlit 기본 페이지 설정
# ==========================================
st.set_page_config(
    page_title="수위 및 보조관측망 모니터링", page_icon="📈", layout="wide"
)

st.title("📊 보조관측망 및 수위 대시보드")
st.markdown("---")

# ==========================================
# 3. 사이드바 (관정 및 연도별 조사 필터 복원)
# ==========================================
st.sidebar.header("🔍 조회 필터")
region = st.sidebar.selectbox("관측 지역 선택", ["고양", "서울", "인천", "기타"])

# 💡 '관정' 선택 기능 복원
well_options = ["제1관정", "제2관정", "제3관정", "보조관정 A"]
selected_well = st.sidebar.selectbox("관정 선택", well_options)

# 💡 '연도별 조사(연도변조사)' 기능 복원
year_options = [2026, 2025, 2024, 2023]
selected_year = st.sidebar.selectbox("연도별 조사 선택", year_options)

# ==========================================
# 4. 데이터 처리 및 출력 영역
# ==========================================
try:
  st.subheader(
      f"📍 {region} 지역 - [{selected_well}] ({selected_year}년 연도별 조사"
      " 현황)"
  )

  # 예시 데이터 (실제 프로젝트의 데이터 로드 로직으로 대체해서 사용하세요)
  data = {
      "측정 시기": ["1분기", "2분기", "3분기", "4분기"],
      "수위 (m)": [1.45, 2.12, 1.88, 1.95],
      "조사 상태": ["완료", "완료", "진행중", "예정"],
  }
  df = pd.DataFrame(data)

  # 데이터프레임 출력 (최신 규격 호환)
  st.dataframe(df, use_container_width=True)

  # ==========================================
  # 5. 시각화 영역 (관정 및 연도별 데이터 그래프)
  # ==========================================
  st.subheader(f"📈 {selected_well} 수위 변화 추이 ({selected_year}년)")

  fig, ax = plt.subplots(figsize=(10, 4))
  ax.plot(
      df["측정 시기"],
      df["수위 (m)"],
      marker="o",
      color="#4C72B0",
      linewidth=2,
      markersize=6,
  )
  ax.set_ylabel("수위 (m)")
  ax.set_title(f"{selected_year}년 {selected_well} 수위 모니터링")
  ax.grid(True, linestyle="--", alpha=0.5)

  # Streamlit에 Matplotlib 차트 렌더링
  st.pyplot(fig)

except Exception as e:
  st.error(f"오류가 발생했습니다: {e}")
