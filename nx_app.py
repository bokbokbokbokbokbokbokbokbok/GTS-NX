# 도면 좌표계 선택 시 WAMIS 표준 대응 옵션 추가
epsg_code = st.selectbox(
    "📍 도면 좌표계 선택 (국가수자원관리시스템/국토정보플랫폼 표준)", 
    options=[
        "epsg:5186 (중부원점 GRS80 - WAMIS/국토정보플랫폼 표준)", 
        "epsg:5179 (UTM-K 통합기준계)", 
        "epsg:5187 (동부원점 GRS80)", 
        "epsg:4326 (WGS84 위경도)"
    ],
    index=0, key='epsg_tab1'
).split(" ")[0]
