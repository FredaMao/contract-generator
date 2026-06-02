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


def make_rpr(font: str) -> str:
    return (f'<w:rPr>'
            f'<w:rFonts w:ascii="{font}" w:eastAsia="{font}" w:hAnsi="{font}" w:cs="{font}"/>'
            f'<w:color w:val="000000"/>'
            f'</w:rPr>')


def sig_para(text: str, font: str = '思源黑體') -> str:
    rpr = make_rpr(font)
    return (
        f'<w:p>{PPR_SIG}'
        f'<w:r>{rpr}'
        f'<w:t xml:space="preserve">{xml_escape(text)}</w:t>'
        f'</w:r></w:p>'
    )


def empty_sig_para() -> str:
    return f'<w:p>{PPR_SIG}</w:p>'


def get_plain_text(xml: str) -> str:
    text = re.sub('<[^>]+>', '', xml)
    return re.sub(r'\s+', ' ', text).strip()


def detect_main_font(xml: str) -> str:
    """Find the most common Chinese font in the document."""
    import collections
    fonts = re.findall(r'w:eastAsia="([^"]+)"', xml)
    if not fonts:
        return '思源黑體'
    skip = {'Noto Sans', 'Arial', 'Times New Roman', 'Calibri', 'Tahoma'}
    filtered = [f for f in fonts if f not in skip]
    candidates = filtered if filtered else fonts
    return collections.Counter(candidates).most_common(1)[0][0]


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


def detect_sig_label_format(xml: str, sig_idx: int, paragraphs: list) -> str:
    """Detect what party label style is used in the signature section."""
    snippet = ' '.join(p[2] for p in paragraphs[sig_idx:min(sig_idx + 15, len(paragraphs))])
    if '甲方（蓋章）' in snippet or '乙方（蓋章）' in snippet:
        return 'stamp'
    if re.search(r'甲\s*方[：:]', snippet) and re.search(r'乙\s*方[：:]', snippet):
        return 'spaced'
    if '甲方名稱' in snippet or '乙方名稱' in snippet:
        return 'name'
    return 'stamp'


def build_signature_section(company: dict, font: str = '思源黑體',
                             label_fmt: str = 'stamp', sig_title: str = '立契約書人') -> str:
    c = company
    u = USPACE

    if label_fmt == 'spaced':
        jia = f'甲　方：{c["name"]}　（以下簡稱甲方）'
        yi  = f'乙　方：{u["name"]}　（以下簡稱乙方）'
        parts = [
            sig_para(sig_title, font),
            empty_sig_para(),
            sig_para(jia, font),
            sig_para(yi, font),
            empty_sig_para(),
            sig_para('中　華　民　國　　　年　　月　　日', font),
        ]
    else:  # stamp / name / default
        jia_label = '甲方名稱：' if label_fmt == 'name' else '甲方（蓋章）：'
        yi_label  = '乙方名稱：' if label_fmt == 'name' else '乙方（蓋章）：'
        parts = [
            sig_para(sig_title, font),
            empty_sig_para(),
            sig_para(f'{jia_label}{c["name"]}', font),
            sig_para(f'負責人/出租人： {c["person"]}', font),
            sig_para(f'身分證字號/統編：{c["id"]}', font),
            sig_para(f'{c["contact_label"]}：{c["contact"]}', font),
            sig_para(f'地址：{c["address"]}', font),
            empty_sig_para(),
            sig_para(f'{yi_label}{u["name"]}', font),
            sig_para(f'負責人/承租人： {u["person"]}', font),
            sig_para(f'身分證字號/統編：{u["id"]}', font),
            sig_para(f'{u["contact_label"]}：{u["contact"]}', font),
            sig_para(f'地址：{u["address"]}', font),
            empty_sig_para(),
            sig_para('中　華　民　國　　　年　　月　　日', font),
        ]
    return ''.join(parts)


def find_sig_section_idx(paragraphs: list, company_name: str) -> int:
    """
    Find the paragraph index where the signature section starts.
    Tries multiple strategies to handle different contract formats.
    Returns -1 if not found.
    """
    n = len(paragraphs)

    # Strategy 1: Find the LAST "立契約書人" / "立補充協議書人" etc.
    # Using LAST occurrence so contracts with both a brief top section and a
    # detailed bottom section (like 補充協議書) use the detailed bottom one.
    SIG_MARKERS = ('立契約書人', '立補充協議書人', '立協議書人', '立合約書人', '立租賃契約書人')
    last_sig = -1
    for i, (_, _, text) in enumerate(paragraphs):
        text_norm = re.sub(r'[　\s]+', '', text)
        if any(m in text_norm for m in SIG_MARKERS):
            last_sig = i
    if last_sig != -1:
        return last_sig

    # Strategy 2: "(簽名頁如後)" → next section is signature page
    for i, (_, _, text) in enumerate(paragraphs):
        if '簽名頁如後' in text:
            # Return next non-empty paragraph
            for j in range(i + 1, n):
                if paragraphs[j][2].strip():
                    return j
            return i + 1

    # Strategy 3: Company name in last 40% of document → scan back for party block start
    start_from = n * 6 // 10
    company_idx = None
    for i in range(start_from, n):
        if company_name in paragraphs[i][2]:
            company_idx = i
            break

    if company_idx is not None:
        # Scan backwards to find the start of the party block
        # Look for a 甲方 label or "下稱" which signals start of party section
        for j in range(company_idx, max(company_idx - 20, start_from - 3) - 1, -1):
            text = paragraphs[j][2].strip()
            if any(kw in text for kw in ['甲方', '出租人', '下稱「甲方', '（甲方）']):
                return j
        # If no label found, go back a few paragraphs from company
        return max(company_idx - 5, start_from)

    # Strategy 4: "中　華　民　國" date line → go back to find party block
    for i in range(n - 1, n * 5 // 10, -1):
        text = paragraphs[i][2]
        if '中' in text and '華' in text and '民' in text and '國' in text and '年' in text:
            # Found date line; scan backwards for party block start
            for j in range(i, max(i - 25, 0) - 1, -1):
                text_j = paragraphs[j][2].strip()
                if any(kw in text_j for kw in ['甲方', '出租人', '立契約書人']):
                    return j
            return max(i - 15, 0)

    return -1


def replace_party_paras_in_place(xml: str, company: dict, sig_idx: int,
                                   paragraphs: list, font: str, label_fmt: str) -> str:
    """
    For top-of-document signatures (only a brief top party section, no bottom section).
    Replaces party VALUES while preserving original labels and suffixes.
    """
    c = company
    u = USPACE
    search_end = min(sig_idx + 25, len(paragraphs))
    to_replace = []

    for abs_i in range(sig_idx, search_end):
        text = paragraphs[abs_i][2].strip()

        # 甲方 paragraph (business owner → company)
        if re.search(r'^(甲[　\s]*方|出租人)[（：:]', text):
            lbl, _, sfx = _split_label_value_suffix(text, c['name'])
            to_replace.append((abs_i, lbl + c['name'] + sfx))

        # 乙方 paragraph with company name (company → 悠勢)
        elif re.search(r'^(乙[　\s]*方|承租人)[（：:]', text) and c['name'] in text:
            lbl, _, sfx = _split_label_value_suffix(text, u['name'])
            to_replace.append((abs_i, lbl + u['name'] + sfx))

    for abs_i, new_text in reversed(to_replace):
        xml = _rebuild_party_para(xml, abs_i, list_paragraphs(xml), new_text, font)

    return xml


def replace_signature_section(xml: str, company: dict, font: str = '思源黑體') -> str:
    """
    Find signature section and update party info.
    - Top-of-doc signatures (補充協議書): only replace the party paragraphs in place.
    - Bottom-of-doc signatures (standard lease): replace from sig_start to body end.
    """
    paragraphs = list_paragraphs(xml)
    company_name = company['name']

    sig_idx = find_sig_section_idx(paragraphs, company_name)
    if sig_idx == -1:
        return xml

    label_fmt = detect_sig_label_format(xml, sig_idx, paragraphs)
    n = len(paragraphs)

    # Signature at top of document → in-place party replacement only
    if sig_idx < n * 0.20:
        return replace_party_paras_in_place(xml, company, sig_idx, paragraphs, font, label_fmt)

    # Signature at bottom → replace everything from sig_start to body end
    sig_start = paragraphs[sig_idx][0]
    body_end_tag = '</w:body>'
    body_end = xml.find(body_end_tag)
    if body_end == -1:
        return xml

    # Don't cut inside a table
    content_before = xml[:sig_start]
    open_tbls = content_before.count('<w:tbl>') + len(re.findall(r'<w:tbl\s', content_before))
    close_tbls = content_before.count('</w:tbl>')
    if open_tbls > close_tbls:
        return xml

    sig_title_text = paragraphs[sig_idx][2].strip() or '立契約書人'
    new_sig = build_signature_section(company, font=font, label_fmt=label_fmt,
                                       sig_title=sig_title_text)

    sect_match = list(re.finditer(r'<w:sectPr[\s>]', xml[sig_start:body_end]))
    if sect_match:
        sect_rel = sect_match[-1].start()
        sect_abs = sig_start + sect_rel
        sect_end = xml.find('</w:sectPr>', sect_abs)
        if sect_end != -1:
            sect_end += 11
            return (xml[:sig_start] + new_sig +
                    xml[sect_abs:sect_end] +
                    body_end_tag + xml[body_end + len(body_end_tag):])

    return xml[:sig_start] + new_sig + body_end_tag + xml[body_end + len(body_end_tag):]


def _split_label_value_suffix(text: str, known_value: str = None) -> tuple:
    """
    Split paragraph text into (label, value, suffix).
    label  = everything up to and including the last ：
    value  = known_value if provided, else content between label and suffix
    suffix = trailing （以下簡稱…）or（下稱…）etc.
    """
    colon_pos = max(text.rfind('：'), text.rfind(':'))
    if colon_pos < 0:
        return text, '', ''
    label = text[:colon_pos + 1]
    rest = text[colon_pos + 1:]
    sfx_match = re.search(r'[　\s]*[（(]', rest)
    if sfx_match:
        suffix = rest[sfx_match.start():]
        value = rest[:sfx_match.start()].strip()
    else:
        suffix = ''
        value = rest.strip()
    return label, known_value if known_value is not None else value, suffix


def _rebuild_party_para(xml: str, para_idx: int, paragraphs: list, new_text: str, font: str) -> str:
    """Replace a single party paragraph with new_text, preserving pPr and rPr."""
    paragraphs = list_paragraphs(xml)
    if para_idx >= len(paragraphs):
        return xml
    ps, pe, _ = paragraphs[para_idx]
    ppr = get_ppr(xml[ps:pe])
    rpr_m = re.search(r'<w:r[\s>].*?<w:rPr>(.*?)</w:rPr>', xml[ps:pe], re.DOTALL)
    rpr = f'<w:rPr>{rpr_m.group(1)}</w:rPr>' if rpr_m else make_rpr(font)
    new_p = (f'<w:p>{ppr}'
             f'<w:r>{rpr}'
             f'<w:t xml:space="preserve">{xml_escape(new_text)}</w:t>'
             f'</w:r></w:p>')
    return xml[:ps] + new_p + xml[pe:]


def update_header_parties(xml: str, company_name: str) -> str:
    """
    Update party names in the contract header/preamble.
    Preserves original labels (甲方/乙方/出租人/承租人/etc.) and suffixes.
    """
    paragraphs = list_paragraphs(xml)
    yi_idx = jia_idx = None

    # Find 乙方 paragraph: has company name AND a party label character
    for i, (_, _, text) in enumerate(paragraphs[:35]):
        if company_name in text and re.search(r'[乙出承][　\s]*(方|租人)[：:]', text):
            yi_idx = i
            break

    if yi_idx is None:
        return xml

    # Find 甲方 paragraph: a nearby paragraph before yi_idx with 甲/出 label
    for i in range(yi_idx - 1, max(-1, yi_idx - 8), -1):
        _, _, text = paragraphs[i]
        if re.search(r'^[甲出][　\s]*(方|租人)[（：:]', text.strip()):
            jia_idx = i
            break

    font = detect_main_font(xml)
    to_update = []

    # 乙方 paragraph → replace company name with 悠勢, preserve label+suffix
    yi_text = paragraphs[yi_idx][2]
    lbl, _, sfx = _split_label_value_suffix(yi_text, USPACE['name'])
    to_update.append((yi_idx, lbl + USPACE['name'] + sfx))

    # 甲方 paragraph → replace business owner with company, preserve label+suffix
    if jia_idx is not None:
        jia_text = paragraphs[jia_idx][2]
        lbl, _, sfx = _split_label_value_suffix(jia_text, company_name)
        to_update.append((jia_idx, lbl + company_name + sfx))

    # Apply later index first
    for idx, new_text in sorted(to_update, key=lambda x: x[0], reverse=True):
        xml = _rebuild_party_para(xml, idx, list_paragraphs(xml), new_text, font)

    return xml


def fill_bank_account(xml: str, company: dict) -> str:
    """
    Fill 甲方指定匯款銀行帳戶 with company bank info.
    Handles both table format (租金) and paragraph format (分潤).
    """
    if 'bank' not in company:
        return xml

    marker = xml.find('甲方指定匯款銀行帳戶')
    if marker == -1:
        return xml

    values = [company['bank'], company['account_name'], company['account_no']]
    tbl_start = xml.find('<w:tbl>', marker)

    # --- 租金版：表格格式 ---
    if tbl_start != -1 and tbl_start < marker + 500:
        tbl_end = xml.find('</w:tbl>', tbl_start) + 8
        tbl_xml = xml[tbl_start:tbl_end]
        new_tbl = tbl_xml
        tr_pos = 0
        row_idx = 0
        rpr = ('<w:rPr>'
               '<w:rFonts w:ascii="Microsoft JhengHei UI" w:eastAsia="Microsoft JhengHei UI"'
               ' w:hAnsi="Microsoft JhengHei UI" w:cs="思源黑體"/>'
               '<w:color w:val="000000"/>'
               '</w:rPr>')
        while row_idx < len(values):
            tr_start = new_tbl.find('<w:tr', tr_pos)
            if tr_start == -1:
                break
            tr_end = new_tbl.find('</w:tr>', tr_start) + 7
            tr_xml = new_tbl[tr_start:tr_end]
            tc1_end = tr_xml.find('</w:tc>') + 7
            tc2_start = tr_xml.find('<w:tc', tc1_end)
            tc2_end = tr_xml.find('</w:tc>', tc2_start) + 7
            if tc2_start == -1:
                tr_pos = tr_end
                row_idx += 1
                continue
            tc2_xml = tr_xml[tc2_start:tc2_end]
            p_start = tc2_xml.find('<w:p')
            p_end = tc2_xml.find('</w:p>', p_start) + 6
            ppr = get_ppr(tc2_xml[p_start:p_end])
            new_p = (f'<w:p>{ppr}<w:r>{rpr}'
                     f'<w:t xml:space="preserve">{xml_escape(values[row_idx])}</w:t>'
                     f'</w:r></w:p>')
            new_tc2 = tc2_xml[:p_start] + new_p + tc2_xml[p_end:]
            new_tr = tr_xml[:tc2_start] + new_tc2 + tr_xml[tc2_end:]
            new_tbl = new_tbl[:tr_start] + new_tr + new_tbl[tr_end:]
            tr_pos = tr_start + len(new_tr)
            row_idx += 1
        return xml[:tbl_start] + new_tbl + xml[tbl_end:]

    # --- 分潤版：段落格式 ---
    # Replace the ENTIRE paragraph so any pre-filled 業主 value is removed.
    # Use list_paragraphs to get exact <w:p> boundaries (avoids hitting <w:pPr>).
    label_value_map = [
        ('銀行名稱（含分行）', '銀行名稱（含分行）：', company['bank']),
        ('帳戶名稱：',         '帳戶名稱：',           company['account_name']),
        ('帳戶號碼：',         '帳戶號碼：',           company['account_no']),
    ]
    search_from = marker
    for search_key, label_text, value in label_value_map:
        # Find the paragraph containing this label using list_paragraphs
        paragraphs = list_paragraphs(xml)
        target = None
        for ps, pe, text in paragraphs:
            if search_key in text and ps >= search_from:
                target = (ps, pe, xml[ps:pe])
                break
        if target is None:
            continue
        p_start, p_end, p_xml = target
        ppr = get_ppr(p_xml)
        # Get run properties from the first <w:r> in the paragraph
        rpr_match = re.search(r'<w:r[\s>].*?<w:rPr>(.*?)</w:rPr>', p_xml, re.DOTALL)
        if rpr_match:
            rpr = f'<w:rPr>{rpr_match.group(1)}</w:rPr>'
        else:
            rpr = RPR_SIG
        # Build clean paragraph: label run + value run (old values discarded)
        new_p = (f'<w:p>{ppr}'
                 f'<w:r>{rpr}<w:t xml:space="preserve">{xml_escape(label_text)}</w:t></w:r>'
                 f'<w:r>{rpr}<w:t xml:space="preserve">{xml_escape(value)}</w:t></w:r>'
                 f'</w:p>')
        xml = xml[:p_start] + new_p + xml[p_end:]
        search_from = p_start + len(new_p)

    return xml


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

    font = detect_main_font(xml)
    xml = update_header_parties(xml, company_name)
    xml = fill_bank_account(xml, company)
    xml = replace_signature_section(xml, company, font=font)

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
