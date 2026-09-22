if 'bldg_data' in st.session_state and st.session_state['bldg_data']:
            bldg_data = st.session_state['bldg_data']
            buffer_poly_wgs84 = st.session_state['buffer_poly_wgs84']
            multi_line_wgs84 = st.session_state['multi_line_wgs84']

            st.success(f"캐드 좌표 매핑 완료 및 씨리얼(Seereal) 대장 정밀 연동 완료! / 반경 내 건축물 {len(bldg_data)}동 검색됨")
            
            # 지도 상단에 강조된 퀵 줌인 선택 박스 배치
            st.markdown("### 🎯 대상 건축물 퀵 줌인 컨트롤러")
            st.write("원하시는 건물의 **연번과 명칭**을 선택하시면 지도가 해당 건물 위치로 즉시 확대(줌인)됩니다.")
            
            bldg_options = {0: "🗺️ 전체 노선 및 반경 범위 보기 (기본)"}
            for b in bldg_data:
                bldg_options[b['연번']] = f"연번 {b['연번']}번 - {b['명칭']} ({b['도로명']})"

            selected_bldg_id = st.selectbox(
                "조회할 건축물 선택",
                options=list(bldg_options.keys()),
                format_func=lambda x: bldg_options[x],
                key='selected_bldg_jump'
            )

            # 선택된 번호에 따른 지도 중심 및 고배율 줌인 설정
            map_center = [st.session_state['project_center'][0], st.session_state['project_center'][1]]
            map_zoom = 17
            
            if selected_bldg_id > 0:
                target_bldg = next((b for b in bldg_data if b['연번'] == selected_bldg_id), None)
                if target_bldg:
                    map_center = [target_bldg['lat'], target_bldg['lon']]
                    map_zoom = 20  # 건물이 꽉 차게 확대

            m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="OpenStreetMap")
            folium.GeoJson(buffer_poly_wgs84, style_function=lambda x: {'fillColor': 'blue', 'color': 'blue', 'weight': 1, 'fillOpacity': 0.2}).add_to(m)
            folium.GeoJson(multi_line_wgs84, style_function=lambda x: {'color': 'red', 'weight': 3}).add_to(m)
            
            for bldg in bldg_data:
                is_selected = (selected_bldg_id == bldg['연번'])
                fill_color = 'orange' if is_selected else 'yellow'
                line_color = 'red' if is_selected else 'black'
                line_weight = 3 if is_selected else 1

                folium.Polygon(
                    locations=[(lat, lon) for lon, lat in bldg['polygon']], 
                    color=line_color, weight=line_weight, fillColor=fill_color, fillOpacity=0.7
                ).add_to(m)
                
                number_icon = folium.DivIcon(html=f"""<div style="background-color: {'#e74c3c' if is_selected else 'white'}; border: 2px solid #e74c3c; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: {'white' if is_selected else '#e74c3c'}; font-size: 12px; margin-left: -12px; margin-top: -12px;">{bldg['연번']}</div>""")
                folium.Marker(location=[bldg['lat'], bldg['lon']], icon=number_icon, tooltip=f"연번 {bldg['연번']} ({bldg['명칭']})").add_to(m)
            
            # [핵심 수정 적용] st_folium에 center와 zoom 명시적 전달
            st_folium(
                m, 
                width="100%", 
                height=500, 
                center=map_center, 
                zoom=map_zoom, 
                returned_objects=[]
            )
            
            df_result = pd.DataFrame(bldg_data)[["연번", "명칭", "도로명", "지번", "구조형식", "높이(m)\n(건축면적, m2)", "층수\n(지하/지상)", "용도", "준공년도", "기한", "등급", "기초형식\n(내진설계)", "건축물대장\n유무", "도면\n보유현황", "비고(지역 및 구역 등)"]]
            st.markdown("### 📊 연도변조사 대상 건축물 현황표 (수정 불가 완벽 조회 전용)")
            st.table(df_result)
