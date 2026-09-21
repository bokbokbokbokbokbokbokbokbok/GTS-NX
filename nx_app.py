import ezdxf

def process_building_dxf(file_input):
    """
    Streamlit DXF 업로드 파일에서 건물 레이어의 POLYLINE, LWPOLYLINE, HATCH 좌표를 안전하게 추출하는 함수
    """
    try:
        # Streamlit UploadedFile 객체 또는 파일 경로 처리
        doc = ezodxf.read(file_input)
    except Exception as e:
        print(f"DXF 읽기 오류: {e}")
        return []

    msp = doc.modelspace()
    buildings = []

    for entity in msp:
        # 건물 레이어 또는 관련 도면 객체 탐색 (필요 시 레이어 이름 조건 추가 가능)
        dxftype = entity.dxftype()
        pts = []

        # 1. 2D/3D POLYLINE 처리
        if dxftype == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices()]

        # 2. LWPOLYLINE (경량 폴리라인) 처리
        elif dxftype == 'LWPOLYLINE':
            # get_points()는 (x, y, start_width, end_width, bulge)를 반환하므로 (x, y)만 추출
            raw_pts = entity.get_points()
            pts = [(p[0], p[1]) for p in raw_pts]

        # 3. HATCH (해치) 처리 - TypeError 원인 해결 구문
        elif dxftype == 'HATCH':
            for path in entity.paths:
                # Path 형태가 PolylinePath인 경우
                if hasattr(path, 'vertices') and path.vertices:
                    pts.extend([(v[0], v[1]) for v in path.vertices])
                
                # Path 형태가 EdgePath인 경우 (LineEdge, ArcEdge 등)
                elif hasattr(path, 'edges') and path.edges:
                    for edge in path.edges:
                        # LineEdge 형태 처리
                        if hasattr(edge, 'start') and hasattr(edge, 'end'):
                            pts.append((edge.start[0], edge.start[1]))
                            pts.append((edge.end[0], edge.end[1]))
                        # ArcEdge / EllipseEdge 형태 처리
                        elif hasattr(edge, 'center'):
                            pts.append((edge.center[0], edge.center[1]))

        # 좌표 추출에 성공한 경우만 건물 데이터 목록에 추가
        if pts:
            buildings.append({
                'id': entity.dxf.handle if hasattr(entity.dxf, 'handle') else None,
                'layer': entity.dxf.layer if hasattr(entity.dxf, 'layer') else '0',
                'type': dxftype,
                'coordinates': pts
            })

    return buildings
