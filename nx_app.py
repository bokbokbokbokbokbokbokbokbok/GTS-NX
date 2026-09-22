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
# 3. 탭 구조 구성 (관측망, 관정, 연도변조사 복원)
# ==========================================
tab1, tab2, tab3 = st.tabs(
    ["📈 관측망 현황", "🔍 관정 관리", "📅 연도변조사"]
)

# [Tab 1] 관측망 현황
with tab1:
  st.subheader("보조관측망 전체 현황")
  region = st.selectbox(
      "관측 지역 선택", ["고양", "서울", "인천", "기타"], key="tab1_region"
  )

  try:
    data1 = {
        "관측소명": [
            f"{region} 제1관측소",
            f"{region} 제2관측소",
            f"{region} 제3관측소",
        ],
        "현재 수위 (m)": [1.45, 2.12, 1.88],
        "상태": ["정상", "주의", "정상"],
    }
    df1 = pd.DataFrame(data1)
    st.dataframe(df1, use_container_width=True)
  except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")

# [Tab 2] 관정 관리
with tab2:
  st.subheader("관정별 상세 정보 관리")
  selected_well = st.selectbox(
      "관정 선택",
      ["제1관정", "제2관정", "제3관정", "보조관정 A"],
      key="tab2_well",
  )

  try:
    st.write(f"현재 선택된 **{selected_well}**의 상세 제원 정보입니다.")
    data2 = {
        "항목": ["심도 (m)", "구경 (mm)", "설치일자", "운영 상태"],
        "내용": ["150m", "200mm", "2020-05-12", "가동중"],
    }
    df2 = pd.DataFrame(data2)
    st.dataframe(df2, use_container_width=True)
  except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")

# [Tab 3] 연도변조사 (연도별 조사 데이터 및 시각화)
with tab3:
  st.subheader("📅 연도변조사 (연도별 조사 데이터)")
  selected_year = st.selectbox(
      "조사 연도 선택", [2026, 2025, 2024, 2023], key="tab3_year"
  )

  try:
    data_year = {
        "분기/시기": ["1분기", "2분기", "3분기", "4분기"],
        "평균 수위 (m)": [1.50, 1.85, 2.05, 1.70],
        "조사 결과": ["적정", "주의", "경계", "적정"],
    }
    df_year = pd.DataFrame(data_year)

    st.dataframe(df_year, use_container_width=True)

    # 연도변조사 시각화 그래프
    st.markdown(f"### 📈 {selected_year}년도 연도변조사 수위 추이")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(
        df_year["분기/시기"],
        df_year["평균 수위 (m)"],
        marker="o",
        color="#2ca02c",
        linewidth=2,
        markersize=6,
    )
    ax.set_ylabel("수위 (m)")
    ax.set_title(f"{selected_year}년 연도변조사 모니터링 그래프")
    ax.grid(True, linestyle="--", alpha=0.5)

    st.pyplot(fig)
  except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")
