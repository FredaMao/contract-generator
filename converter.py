import zipfile
import re
import io
import xml.etree.ElementTree as ET
from typing import Optional

COMPANIES = {
    '志昌資產管理有限公司': {
        'name': '志昌資產管理有限公司',
        'person': '謝昌志',
        'id': '90634048',
        'contact_label': '聯絡電話',
        'contact': '0917-444-186',
        'address': '臺北市中山區長安東路2段80號10樓之1',
        'bank': '國泰世華銀行 慶城分行',
        'account_name': '志昌資產管理有限公司',
        'account_no': '268035011822',
    },
    '瀚昱開發股份有限公司': {
        'name': '瀚昱開發股份有限公司',
        'person': '錢漢洲',
        'id': '62205204',
        'contact_label': '電子郵件',
        'contact': 'service@hanyudev.com',
        'address': '臺北市中山區松江路50號9樓',
        'bank': '凱基商業銀行 城東分行',
        'account_name': '瀚昱開發股份有限公司',
        'account_no': '60070100034483',
    },
    '毅源開發股份有限公司': {
        'name': '毅源開發股份有限公司',
        'person': '吳品毅',
        'id': '62204330',
        'contact_label': '電子郵件',
        'contact': 'service@yiyuandev.com',
        'address': '臺北市松山區寶清街21號4樓之1',
        'bank': '凱基商業銀行 城東分行',
        'account_name': '毅源開發股份有限公司',
        'account_no': '60070100034496',
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


def xml_escape(text: str) -> str:
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def sig_para(text: str) -> str:
    return (
        f'<w:p>{PPR_SIG}'
        f'<w:r>{RPR_SIG}'
        f'<w:t xml:space="preserve">{xml_escape(text)}</w:t>'
        f'</w:r></w:p>'
    )


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
    """Return list of (start, end, plain_text) for all top-level paragraphs."""
    result = []
    pos = 0
    while True:
        start = xml.find('<w:p', pos)
        if start == -1:
            break
        # Only match <w:p> or <w:p ...>, not <w:pPr>, <w:pStyle>, etc.
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
    """Extract <w:pPr>...</w:pPr> from a paragraph, or return default."""
    for tag in ('<w:pPr>', '<w:pPr '):
        start = para_xml.find(tag)
        if start != -1:
            end = para_xml.find('</w:pPr>')
            if end != -1:
                return para_xml[start:end + 8]
    return PPR_SIG


def build_header_para(ppr: str, label_value: str, suffix: str) -> str:
    spaces = '                                         '
    return (
        f'<w:p>{ppr}'
        f'<w:r>{RPR_SIG}'
        f'<w:t xml:space="preserve">{xml_escape(label_value)}</w:t>'
        f'</w:r>'
        f'<w:r>{RPR_SIG}'
        f'<w:t xml:space="preserve">{spaces}{xml_escape(suffix)}</w:t>'
        f'</w:r>'
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


def replace_signature_section(xml: str, company: dict) -> str:
    """Find 立契約書人 paragraph and replace everything after it."""
    paragraphs = list_paragraphs(xml)

    sig_para_idx = None
    for i, (start, end, text) in enumerate(paragraphs):
        if '立契約書人' in text:
            sig_para_idx = i
            break

    if sig_para_idx is None:
        return xml  # Can't find signature section, return unchanged

    sig_start = paragraphs[sig_para_idx][0]
    body_end_tag = '</w:body>'
    body_end = xml.find(body_end_tag)
    if body_end == -1:
        return xml

    # Check we're not inside a table
    content_before = xml[:sig_start]
    open_tbls = content_before.count('<w:tbl>') + len(re.findall(r'<w:tbl\s', content_before))
    close_tbls = content_before.count('</w:tbl>')
    if open_tbls > close_tbls:
        # Signature section is inside a table — skip replacement
        return xml

    # Preserve <w:sectPr> if present (page layout settings)
    sect_match = list(re.finditer(r'<w:sectPr[\s>]', xml[sig_start:body_end]))
    new_sig = build_signature_section(company)

    if sect_match:
        # Use the LAST sectPr occurrence
        sect_rel_start = sect_match[-1].start()
        sect_abs_start = sig_start + sect_rel_start
        sect_abs_end = xml.find('</w:sectPr>', sect_abs_start)
        if sect_abs_end != -1:
            sect_abs_end += 11  # len('</w:sectPr>')
            return (xml[:sig_start] + new_sig +
                    xml[sect_abs_start:sect_abs_end] +
                    body_end_tag + xml[body_end + len(body_end_tag):])

    return xml[:sig_start] + new_sig + body_end_tag + xml[body_end + len(body_end_tag):]


def update_header_parties(xml: str, company_name: str) -> str:
    """Update 出租人 / 承租人 lines in the contract header."""
    paragraphs = list_paragraphs(xml)
    out_idx = in_idx = None

    for i, (_, _, text) in enumerate(paragraphs[:30]):
        if '出租人：' in text and '下稱' in text and out_idx is None:
            out_idx = i
        if '承租人：' in text and '下稱' in text and in_idx is None:
            in_idx = i

    if out_idx is None or in_idx is None:
        return xml

    # Process later index first so earlier positions remain valid
    order = sorted([(in_idx, f'承租人：{USPACE["name"]}', '（下稱「乙方」）'),
                    (out_idx, f'出租人：{company_name}', '（下稱「甲方」）')],
                   key=lambda x: x[0], reverse=True)

    for target_idx, label_value, suffix in order:
        paragraphs = list_paragraphs(xml)
        if target_idx >= len(paragraphs):
            continue
        ps, pe, _ = paragraphs[target_idx]
        ppr = get_ppr(xml[ps:pe])
        new_para = build_header_para(ppr, label_value, suffix)
        xml = xml[:ps] + new_para + xml[pe:]

    return xml


def fill_bank_account_table(xml: str, company: dict) -> str:
    """
    Find the 甲方指定匯款銀行帳戶 table and fill the right column cells
    with the company's bank account info.
    Table rows (in order): 銀行名稱（含分行）, 帳戶名稱, 帳戶號碼
    """
    if 'bank' not in company:
        return xml

    marker = xml.find('甲方指定匯款銀行帳戶')
    if marker == -1:
        return xml

    tbl_start = xml.find('<w:tbl>', marker)
    if tbl_start == -1:
        return xml
    tbl_end = xml.find('</w:tbl>', tbl_start) + 8
    tbl_xml = xml[tbl_start:tbl_end]

    values = [company['bank'], company['account_name'], company['account_no']]

    # Find each <w:tr> in the table and fill its second <w:tc>
    new_tbl = tbl_xml
    tr_pos = 0
    row_idx = 0
    while row_idx < len(values):
        tr_start = new_tbl.find('<w:tr ', tr_pos)
        if tr_start == -1:
            tr_start = new_tbl.find('<w:tr>', tr_pos)
        if tr_start == -1:
            break
        tr_end = new_tbl.find('</w:tr>', tr_start) + 7
        tr_xml = new_tbl[tr_start:tr_end]

        # Find the second <w:tc> (value column)
        tc1_end = tr_xml.find('</w:tc>') + 7
        tc2_start = tr_xml.find('<w:tc', tc1_end)
        tc2_end = tr_xml.find('</w:tc>', tc2_start) + 7

        if tc2_start == -1 or tc2_end == -1:
            tr_pos = tr_end
            row_idx += 1
            continue

        tc2_xml = tr_xml[tc2_start:tc2_end]

        # Find the <w:p> inside this cell and replace its content
        p_start = tc2_xml.find('<w:p')
        p_end = tc2_xml.find('</w:p>', p_start) + 6
        p_xml = tc2_xml[p_start:p_end]
        ppr = get_ppr(p_xml)

        rpr = ('<w:rPr>'
               '<w:rFonts w:ascii="Microsoft JhengHei UI" w:eastAsia="Microsoft JhengHei UI"'
               ' w:hAnsi="Microsoft JhengHei UI" w:cs="思源黑體"/>'
               '<w:color w:val="000000"/>'
               '</w:rPr>')
        new_p = (f'<w:p>{ppr}'
                 f'<w:r>{rpr}'
                 f'<w:t xml:space="preserve">{xml_escape(values[row_idx])}</w:t>'
                 f'</w:r></w:p>')

        new_tc2 = tc2_xml[:p_start] + new_p + tc2_xml[p_end:]
        new_tr = tr_xml[:tc2_start] + new_tc2 + tr_xml[tc2_end:]
        new_tbl = new_tbl[:tr_start] + new_tr + new_tbl[tr_end:]

        tr_pos = tr_start + len(new_tr)
        row_idx += 1

    return xml[:tbl_start] + new_tbl + xml[tbl_end:]


def validate_xml(xml_str: str) -> None:
    """Raise ValueError if XML is not well-formed."""
    try:
        # Register common OOXML namespaces to avoid parse errors
        ET.fromstring(xml_str.encode('utf-8'))
    except ET.ParseError as e:
        raise ValueError(f'合約 XML 格式有誤，無法轉換此檔案（{e}）')


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

    xml = update_header_parties(xml, company_name)
    xml = fill_bank_account_table(xml, company)
    xml = replace_signature_section(xml, company)

    validate_xml(xml)

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
