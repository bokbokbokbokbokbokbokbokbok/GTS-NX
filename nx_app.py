# 올바른 코드
@classmethod
def from_mct_text(cls, mct_content: str):
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
