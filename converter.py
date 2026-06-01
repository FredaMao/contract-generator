import zipfile
import re
import io
from typing import Optional

COMPANIES = {
    '志昌資產管理有限公司': {
        'name': '志昌資產管理有限公司',
        'person': '謝昌志',
        'id': '90634048',
        'contact_label': '聯絡電話',
        'contact': '0917-444-186',
        'address': '臺北市中山區長安東路2段80號10樓之1',
    },
    '瀚昱開發股份有限公司': {
        'name': '瀚昱開發股份有限公司',
        'person': '錢漢洲',
        'id': '62205204',
        'contact_label': '電子郵件',
        'contact': 'service@hanyudev.com',
        'address': '臺北市中山區松江路50號9樓',
    },
    '毅源開發股份有限公司': {
        'name': '毅源開發股份有限公司',
        'person': '吳品毅',
        'id': '62204330',
        'contact_label': '電子郵件',
        'contact': 'service@yiyuandev.com',
        'address': '臺北市松山區寶清街21號4樓之1',
    },
}

USPACE = {
    'name': '悠勢科技股份有限公司',
    'person': '宋捷仁',
    'id': '52492792',
    'contact_label': '聯絡電話',
    'contact': '02-7751-8097',
    'address': '臺北市中山區八德路二段232號9樓',
}

PPR_SIG = (
    '<w:pPr>'
    '<w:spacing w:line="420" w:lineRule="auto"/>'
    '<w:jc w:val="both"/>'
    '<w:rPr>'
    '<w:rFonts w:ascii="思源黑體" w:eastAsia="思源黑體" w:hAnsi="思源黑體" w:cs="思源黑體"/>'
    '<w:color w:val="000000"/>'
    '</w:rPr>'
    '</w:pPr>'
)
RPR_SIG = (
    '<w:rPr>'
    '<w:rFonts w:ascii="思源黑體" w:eastAsia="思源黑體" w:hAnsi="思源黑體" w:cs="思源黑體"/>'
    '<w:color w:val="000000"/>'
    '</w:rPr>'
)


def sig_para(text: str) -> str:
    return f'<w:p>{PPR_SIG}<w:r>{RPR_SIG}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def empty_sig_para() -> str:
    return f'<w:p>{PPR_SIG}</w:p>'


def get_plain_text(xml: str) -> str:
    text = re.sub('<[^>]+>', '', xml)
    return re.sub(r'\s+', ' ', text).strip()


def detect_company(plain_text: str) -> Optional[str]:
    for name in COMPANIES:
        if name in plain_text:
            return name
    return None


def list_paragraphs(xml: str) -> list:
    result = []
    pos = 0
    while True:
        start = xml.find('<w:p', pos)
        if start == -1:
            break
        if len(xml) > start + 4 and xml[start + 4] not in (' ', '>'):
            pos = start + 4
            continue
        end = xml.find('</w:p>', start)
        if end == -1:
            break
        end += 6
        para_xml = xml[start:end]
        text = re.sub('<[^>]+>', '', para_xml)
        text = re.sub(r'\s+', ' ', text).strip()
        result.append((start, end, text))
        pos = end
    return result


def get_ppr(para_xml: str) -> str:
    for tag in ('<w:pPr>', '<w:pPr '):
        start = para_xml.find(tag)
        if start != -1:
            end = para_xml.find('</w:pPr>') + 8
            return para_xml[start:end]
    return PPR_SIG


def build_header_para(ppr: str, label_value: str, suffix: str) -> str:
    spaces = '                                         '
    return (
        f'<w:p>{ppr}'
        f'<w:r>{RPR_SIG}<w:t xml:space="preserve">{label_value}</w:t></w:r>'
        f'<w:r>{RPR_SIG}<w:t xml:space="preserve">{spaces}{suffix}</w:t></w:r>'
        f'</w:p>'
    )


def build_signature_section(company: dict) -> str:
    c = company
    u = USPACE
    parts = [
        sig_para('立契約書人'),
        empty_sig_para(),
        sig_para(f'甲方（蓋章）：{c["name"]}'),
        sig_para(f'負責人/出租人： {c["person"]}'),
        sig_para(f'身分證字號/統編：{c["id"]}'),
        sig_para(f'{c["contact_label"]}：{c["contact"]}'),
        sig_para(f'地址：{c["address"]}'),
        empty_sig_para(),
        sig_para(f'乙方（蓋章）：{u["name"]}'),
        sig_para(f'負責人/承租人： {u["person"]}'),
        sig_para(f'身分證字號/統編：{u["id"]}'),
        sig_para(f'{u["contact_label"]}：{u["contact"]}'),
        sig_para(f'地址：{u["address"]}'),
        empty_sig_para(),
        sig_para('中　華　民　國　　　年　　月　　日'),
    ]
    return ''.join(parts)


def convert_contract(docx_bytes: bytes, original_filename: str) -> tuple:
    """
    Convert a 對業主 contract to a 對悠勢 contract.
    Returns (output_bytes, output_filename).
    Raises ValueError for user-facing errors.
    """
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        xml = z.read('word/document.xml').decode('utf-8')

    plain = get_plain_text(xml)
    company_name = detect_company(plain)
    if not company_name:
        raise ValueError('無法識別合約中的公司（志昌／瀚昱／毅源），請確認上傳的是對業主合約')

    company = COMPANIES[company_name]

    # --- Update header 出租人 / 承租人 ---
    paragraphs = list_paragraphs(xml)
    out_idx = in_idx = None
    for i, (_, _, text) in enumerate(paragraphs[:25]):
        if '出租人：' in text and '下稱' in text and out_idx is None:
            out_idx = i
        if '承租人：' in text and '下稱' in text and in_idx is None:
            in_idx = i

    if out_idx is not None and in_idx is not None:
        # Replace 承租人 first (farther down), then 出租人
        for target_idx, label_value, suffix in [
            (in_idx, f'承租人：{USPACE["name"]}', '（下稱「乙方」）'),
            (out_idx, f'出租人：{company_name}', '（下稱「甲方」）'),
        ]:
            ps, pe, _ = paragraphs[target_idx]
            ppr = get_ppr(xml[ps:pe])
            new_para = build_header_para(ppr, label_value, suffix)
            xml = xml[:ps] + new_para + xml[pe:]
            paragraphs = list_paragraphs(xml)

    # --- Replace signature section ---
    sig_marker = xml.find('立契約書人')
    if sig_marker != -1:
        sig_start = xml.rfind('<w:p', 0, sig_marker)
        body_end = xml.find('</w:body>')

        # Preserve <w:sectPr> (page layout) if present after signature start
        sect_idx = xml.rfind('<w:sectPr', sig_start, body_end)
        new_sig = build_signature_section(company)

        if sect_idx != -1:
            sect_end = xml.find('</w:sectPr>', sect_idx) + 11
            xml = xml[:sig_start] + new_sig + xml[sect_idx:sect_end] + '</w:body>' + xml[body_end + 9:]
        else:
            xml = xml[:sig_start] + new_sig + '</w:body>' + xml[body_end + 9:]

    # --- Build output docx ---
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(docx_bytes), 'r') as zin, \
         zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                data = xml.encode('utf-8')
            zout.writestr(item, data)

    base = original_filename[:-5] if original_filename.lower().endswith('.docx') else original_filename
    output_filename = f'{base}(對悠勢合約).docx'

    return output.getvalue(), output_filename
