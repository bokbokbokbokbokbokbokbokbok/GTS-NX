import os
import platform
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
import pandas as pd
import streamlit as st

# ==========================================
# 1. 한글 폰트 설정 (OS별 자동 대응 및 서버 호환)
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
# 3. 사이드바 구성
# ==========================================
st.sidebar.header("🔍 조회 필터")
region = st.sidebar.selectbox("관측 지역 선택", ["고양", "서울", "인천", "기타"])

# ==========================================
# 4. 데이터 처리 및 출력 영역
# ==========================================
try:
  # 예시 데이터 (실제 프로젝트 데이터 로드 코드로 대체 가능)
  data = {
      "관측소명": [
          f"{region} 제1관측소",
          f"{region} 제2관측소",
          f"{region} 제3관측소",
      ],
      "현재 수위 (m)": [1.45, 2.12, 1.88],
      "상태": ["정상", "주의", "정상"],
  }
  df = pd.DataFrame(data)

  st.subheader(f"📍 {region} 지역 관측망 데이터 현황")

  # 데이터프레임 출력 (최신 Streamlit 규격 적용)
  st.dataframe(df, use_container_width=True)

  # ==========================================
  # 5. 시각화 영역
  # ==========================================
  st.subheader("📈 관측소별 수위 비교 그래프")

  fig, ax = plt.subplots(figsize=(10, 4))
  ax.bar(df["관측소명"], df["현재 수위 (m)"], color="#4C72B0")
  ax.set_ylabel("수위 (m)")
  ax.set_title("관측소별 수위 현황")

  st.pyplot(fig)

except Exception as e:
  st.error(f"오류가 발생했습니다: {e}")
