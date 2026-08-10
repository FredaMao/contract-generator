import io
import os
import random
import re
import zipfile
from docxtpl import DocxTemplate
from converter import xml_escape, list_paragraphs

FONT = '標楷體'

NEW_DIR = os.path.join(os.path.dirname(__file__), '自動產生合約範本', 'NEW')

TEMPLATES = {
    '悠勢': '悠勢-業主_停車場系統管理與技術服務合作協議書_公版_7.14.docx',
    '志昌': '志昌-業主_停車場系統管理與技術服務合作協議書_公版_7.7.docx',
    '瀚昱': '瀚昱-業主_停車場系統管理與技術服務合作協議書_公版_7.7.docx',
    '毅源': '毅源-業主_停車場系統管理與技術服務合作協議書_公版_7.7.docx',
}

COMPANIES = {
    '志昌': {
        'name': '志昌資產管理股份有限公司',
        'owner': '連偉策',
        'id': '90634048',
        'phone': '',
        'address': '臺北市中山區長安東路2段80號10樓之1',
        'email': 'service@zcasset.com.tw',
    },
    '瀚昱': {
        'name': '瀚昱開發股份有限公司',
        'owner': '錢漢洲',
        'id': '62205204',
        'phone': '',
        'address': '臺北市中山區松江路50號9樓',
        'email': 'service@hanyudev.com',
    },
    '毅源': {
        'name': '毅源開發股份有限公司',
        'owner': '吳品毅',
        'id': '62204330',
        'phone': '',
        'address': '臺北市松山區寶清街21號4樓之1',
        'email': 'service@yiyuandev.com',
    },
}

_OPTIONAL_BLANKS = {
    'spots':                  '____',
    'amount':                 '________',
    'deposit':                '0',
    'pay_freq':               '月結',
    'pay_period':             '一（1）',
    'pay_method':             '匯款',
    'min_guarantee':          '________',
    'excess_threshold':       '________',
    'excess_party_a_percent': '__',
    'excess_party_b_percent': '__',
    'party_a_percent':        '__',
    'party_b_percent':        '__',
    'bank_name':              '____________________',
    'account_name':           '____________________',
    'account_number':         '____________________',
    'phone':                  '______________',
    'email':                  '____________________',
    'start_date':             '____年__月__日',
    'end_date':               '____年__月__日',
    'sign_date':              '____年__月__日',
}


def date_to_minguo(date_str: str) -> str:
    """Convert YYYY-MM-DD to 民國YYY年M月D日"""
    if not date_str:
        return ''
    try:
        y, m, d = date_str.split('-')
        return f'{int(y) - 1911}年{int(m)}月{int(d)}日'
    except Exception:
        return date_str


def _rfonts_replacement(_m: re.Match) -> str:
    return (f'<w:rFonts w:ascii="{FONT}" w:eastAsia="{FONT}" '
            f'w:hAnsi="{FONT}" w:cs="{FONT}"/>')


def _apply_font_xml(xml: str) -> str:
    xml = re.sub(r'<w:rFonts\b.*?/>', _rfonts_replacement, xml, flags=re.DOTALL)
    xml = re.sub(r'<w:highlight\b[^/]*/>', '', xml)
    xml = re.sub(r'<w:shd\b[^/]*/>', '', xml, flags=re.DOTALL)
    return xml


def _override_fonts(docx_bytes: bytes) -> bytes:
    in_buf = io.BytesIO(docx_bytes)
    out_buf = io.BytesIO()
    font_targets = {'word/document.xml', 'word/styles.xml'}
    with zipfile.ZipFile(in_buf) as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith('.xml'):
                    xml_str = data.decode('utf-8')
                    if item.filename in font_targets:
                        xml_str = _apply_font_xml(xml_str)
                    # Normalise all ballot-box characters to filled/empty squares
                    xml_str = xml_str.replace('☑', '■').replace('☐', '□')
                    data = xml_str.encode('utf-8')
                zout.writestr(item, data)
    return out_buf.getvalue()


_PARTY_SFX_PAT = re.compile(r'[（(][^）)]{0,30}[甲乙][　\s]*方[^）)]{0,10}[）)]')
_DATE_PAT = re.compile(r'中[　 ]*華[　 ]*民[　 ]*國')


def _rebuild_para_text(xml: str, ps: int, pe: int, new_text: str, size: int = 0) -> str:
    para_xml = xml[ps:pe]
    ppr_m = re.search(r'<w:pPr[\s>].*?</w:pPr>', para_xml, re.DOTALL)
    ppr = ppr_m.group(0) if ppr_m else ''
    rpr_m = re.search(r'<w:r[\s>].*?<w:rPr>(.*?)</w:rPr>', para_xml, re.DOTALL)
    if not rpr_m:
        rpr_m = re.search(r'<w:rPr>(.*?)</w:rPr>', para_xml, re.DOTALL)
    if rpr_m:
        rpr_content = re.sub(r'<w:sz\b[^/]*/>', '', rpr_m.group(1))
        rpr_content = re.sub(r'<w:szCs\b[^/]*/>', '', rpr_content)
        rpr_content = re.sub(r'<w:u\b[^/]*/>', '', rpr_content)
        if size:
            rpr_content += f'<w:sz w:val="{size * 2}"/><w:szCs w:val="{size * 2}"/>'
        rpr = f'<w:rPr>{rpr_content}</w:rPr>'
    else:
        sz_xml = f'<w:sz w:val="{size * 2}"/><w:szCs w:val="{size * 2}"/>' if size else ''
        rpr = f'<w:rPr>{sz_xml}</w:rPr>' if sz_xml else ''
    new_p = (f'<w:p>{ppr}'
             f'<w:r>{rpr}'
             f'<w:t xml:space="preserve">{xml_escape(new_text)}</w:t>'
             f'</w:r></w:p>')
    return xml[:ps] + new_p + xml[pe:]


def _inject_padding_into_para_sdt(xml: str, ps: int, pe: int, padding: str, suffix: str) -> str:
    """Add padding before suffix within an sdt paragraph by modifying <w:t> only."""
    para_xml = xml[ps:pe]
    t_pat = re.compile(r'(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)', re.DOTALL)
    new_para = para_xml
    for m in reversed(list(t_pat.finditer(para_xml))):
        t_content = m.group(2)
        if suffix in t_content:
            sfx_idx = t_content.find(suffix)
            prefix_part = t_content[:sfx_idx].rstrip('　 ')
            new_content = prefix_part + padding + suffix
            new_para = new_para[:m.start(2)] + new_content + new_para[m.end(2):]
            break
    return xml[:ps] + new_para + xml[pe:]


def _align_party_suffixes(xml: str) -> str:
    """Pad 甲方/乙方 preamble lines so （下稱「X方」） suffixes align."""
    paragraphs = list_paragraphs(xml)
    jia_info = yi_info = None
    for ps, pe, text in paragraphs[:60]:
        m = _PARTY_SFX_PAT.search(text)
        if not m:
            continue
        sfx_text = text[m.start():]
        prefix = text[:m.start()].rstrip('　 ')
        if '甲方' in sfx_text and jia_info is None:
            jia_info = (ps, pe, prefix, sfx_text)
        elif '乙方' in sfx_text and yi_info is None:
            yi_info = (ps, pe, prefix, sfx_text)
    if not jia_info or not yi_info:
        return xml
    jia_ps, jia_pe, jia_pre, jia_sfx = jia_info
    yi_ps, yi_pe, yi_pre, yi_sfx = yi_info
    max_len = max(len(jia_pre), len(yi_pre))
    items = [
        (jia_ps, jia_pe, jia_pre, '　' * (max_len - len(jia_pre)), jia_sfx),
        (yi_ps,  yi_pe,  yi_pre,  '　' * (max_len - len(yi_pre)),  yi_sfx),
    ]
    for ps, pe, pre, padding, sfx in sorted(items, key=lambda x: x[0], reverse=True):
        xml = _rebuild_para_text(xml, ps, pe, pre + padding + sfx)
    return xml


def _apply_date_format(xml: str, sign_date: str = '') -> str:
    """Set signing date line to font size 20; inject sign_date when provided."""
    DATE_TEXT = '中　華　民　國　　　年　　月　　日'
    paragraphs = list_paragraphs(xml)
    # Take the LAST occurrence — the signing date is always at the document end;
    # earlier occurrences (e.g. in article clauses) must not be overwritten.
    last_match = None
    for ps, pe, text in paragraphs:
        if _DATE_PAT.search(text) and '法規' not in text and '法律' not in text:
            last_match = (ps, pe)
    if last_match:
        ps, pe = last_match
        new_text = ('中　華　民　國　' + sign_date) if sign_date else DATE_TEXT
        xml = _rebuild_para_text(xml, ps, pe, new_text, size=20)
    return xml


_SIG_TITLE_PAT = re.compile(r'立(協議|契約|合約|租賃契約)書人')


def _keep_signature_with_date(xml: str) -> str:
    """Glue the signature block to the date line with w:keepNext so Word
    never splits the date onto its own page away from the party info
    (the owner-side templates leave ~12 blank lines for a physical stamp,
    which otherwise pushes the date line past the page boundary)."""
    paragraphs = list_paragraphs(xml)
    n = len(paragraphs)

    sig_idx = None
    for i in range(n - 1, -1, -1):
        if _SIG_TITLE_PAT.search(paragraphs[i][2]):
            sig_idx = i
            break
    if sig_idx is None:
        return xml

    date_idx = None
    for i in range(n - 1, sig_idx, -1):
        text = paragraphs[i][2]
        if _DATE_PAT.search(text) and '法規' not in text and '法律' not in text:
            date_idx = i
            break
    if date_idx is None:
        return xml

    # Chain keepNext across every paragraph from the signature title through
    # the one right before the date line, forming a single unbreakable block.
    for ps, pe, _ in reversed(paragraphs[sig_idx:date_idx]):
        para_xml = xml[ps:pe]
        if '<w:keepNext' in para_xml:
            continue
        ppr_m = re.search(r'<w:pPr\b[^>]*>', para_xml)
        if ppr_m:
            new_para = para_xml[:ppr_m.end()] + '<w:keepNext/>' + para_xml[ppr_m.end():]
        else:
            p_m = re.search(r'<w:p\b[^>]*>', para_xml)
            new_para = (para_xml[:p_m.end()] + '<w:pPr><w:keepNext/></w:pPr>'
                        + para_xml[p_m.end():])
        xml = xml[:ps] + new_para + xml[pe:]

    return xml


def _fix_paragraph_ids(xml: str) -> str:
    """Assign unique w14:paraId and w14:textId values to avoid Word 'unreadable content' warning.

    Google Docs exports use 77777777 as a placeholder textId for every paragraph,
    causing Word to report duplicate paragraph IDs as an OOXML schema violation.
    """
    used: set[str] = set()

    def _new_id() -> str:
        while True:
            hex_id = f'{random.randint(1, 0xFFFFFFFE):08X}'
            if hex_id not in used:
                used.add(hex_id)
                return hex_id

    # Seed with existing non-placeholder IDs so we never collide with them.
    for val in re.findall(r'w14:(?:paraId|textId)="([0-9A-Fa-f]+)"', xml):
        if val.upper() != '77777777':
            used.add(val.upper())

    seen_para: set[str] = set()
    seen_text: set[str] = set()

    def _replace_para_id(m: re.Match) -> str:
        val = m.group(1).upper()
        if val in seen_para:
            return f'w14:paraId="{_new_id()}"'
        seen_para.add(val)
        return m.group(0)

    def _replace_text_id(m: re.Match) -> str:
        val = m.group(1).upper()
        if val == '77777777' or val in seen_text:
            return f'w14:textId="{_new_id()}"'
        seen_text.add(val)
        return m.group(0)

    xml = re.sub(r'w14:paraId="([0-9A-Fa-f]+)"', _replace_para_id, xml)
    xml = re.sub(r'w14:textId="([0-9A-Fa-f]+)"', _replace_text_id, xml)
    return xml


def _post_process_docx(docx_bytes: bytes, sign_date: str = '') -> bytes:
    """Apply party suffix alignment and standard date line format."""
    in_buf = io.BytesIO(docx_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf) as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'word/document.xml':
                    doc_xml = data.decode('utf-8')
                    doc_xml = _fix_paragraph_ids(doc_xml)
                    doc_xml = _align_party_suffixes(doc_xml)
                    doc_xml = _apply_date_format(doc_xml, sign_date)
                    doc_xml = _keep_signature_with_date(doc_xml)
                    data = doc_xml.encode('utf-8')
                elif item.filename.startswith('word/') and item.filename.endswith('.xml'):
                    xml_str = data.decode('utf-8')
                    if 'w14:paraId' in xml_str or 'w14:textId' in xml_str:
                        xml_str = _fix_paragraph_ids(xml_str)
                        data = xml_str.encode('utf-8')
                zout.writestr(item, data)
    return out_buf.getvalue()


def generate_contract(company_key: str, mode: str, form_data: dict) -> tuple[bytes, str]:
    building_name = form_data.get('building_name', '').strip()
    if not building_name:
        raise ValueError('建物名稱為必填欄位')

    mode = mode.lower()
    if mode not in ('a', 'b', 'c'):
        raise ValueError(f'未知的收益框架模式：{mode}')

    ctx = dict(form_data)

    for field in ('start_date', 'end_date', 'sign_date'):
        ctx[field] = date_to_minguo(ctx.get(field, ''))

    ctx['email'] = ctx.get('a_email', '')

    # Building / header data fields
    ctx['building_id']    = form_data.get('building_id', '').strip()
    ctx['building_name']  = building_name
    ctx['building_phone'] = form_data.get('building_phone', '').strip()
    ctx['sales']          = form_data.get('sales', '').strip()

    # Income code — stored as "類別_代號" e.g. "個人_空地租賃(51L)"
    ic_full = form_data.get('income_code', '').strip()
    ic_display = ic_full.split('_', 1)[1] if '_' in ic_full else ic_full
    ctx['income_code']       = ic_display
    ctx['ic_personal_51L']  = (ic_full == '個人_空地租賃(51L)')
    ctx['ic_personal_51J']  = (ic_full == '個人_建物租賃(51J)')
    ctx['ic_corp_00']       = (ic_full == '法人_00發票')
    ctx['ic_committee_51L'] = (ic_full == '管委會_空地租賃(51L)')
    ctx['ic_committee_51J'] = (ic_full == '管委會_建物租賃(51J)')
    ctx['ic_committee_00']  = (ic_full == '管委會_00發票')

    # Mode selection checkboxes (body)
    ctx['mode_a_check'] = '■' if mode == 'a' else '□'
    ctx['mode_b_check'] = '■' if mode == 'b' else '□'
    ctx['mode_c_check'] = '■' if mode == 'c' else '□'

    # 竣工圖／繪製圖 checkboxes（悠勢-業主 7.14 範本專用）
    blueprint = form_data.get('blueprint', '').strip()
    ctx['bp_owner_check']  = '■' if blueprint == 'owner' else '□'
    ctx['bp_uspace_check'] = '■' if blueprint == 'uspace' else '□'

    # 水電費負擔方 checkboxes（8.6 水電費條款修正新增）
    utility_payer = form_data.get('utility_payer', '').strip()
    ctx['util_party_a_check'] = '■' if utility_payer == 'a' else '□'
    ctx['util_party_b_check'] = '■' if utility_payer == 'b' else '□'

    # 分潤稅別（模式B、模式C超額部分適用；固定金額/保底金額恆為含稅，不受此影響）
    tax_type = form_data.get('tax_type', '').strip() or '未稅'
    ctx['tax_type'] = tax_type

    # Header checkboxes — 固定 for mode A/C; 分潤依所選稅別 for mode B/C
    ctx['fixed_check']      = '■' if mode in ('a', 'c') else '□'
    ctx['profit_inc_check'] = '■' if (mode in ('b', 'c') and tax_type == '含稅') else '□'
    ctx['profit_exc_check'] = '■' if (mode in ('b', 'c') and tax_type == '未稅') else '□'

    # Mode C fields
    ctx['min_guarantee']          = form_data.get('min_guarantee', '').strip()
    ctx['excess_threshold']       = form_data.get('excess_threshold', '').strip()
    ctx['excess_party_a_percent'] = form_data.get('excess_party_a_percent', '').strip()
    ctx['excess_party_b_percent'] = form_data.get('excess_party_b_percent', '').strip()

    # Template selection（乙方資訊已寫死在各公司範本內，不再需要 party_b 變數）
    tpl_file = TEMPLATES.get(company_key)
    if not tpl_file:
        raise ValueError(f'未知的公司：{company_key}')

    sign_date_raw = ctx.get('sign_date', '')

    for field, blank in _OPTIONAL_BLANKS.items():
        if not str(ctx.get(field, '')).strip():
            ctx[field] = blank

    tpl = DocxTemplate(os.path.join(NEW_DIR, tpl_file))
    tpl.render(ctx)

    buf = io.BytesIO()
    tpl.save(buf)
    docx_bytes = _post_process_docx(buf.getvalue(), sign_date_raw)
    docx_bytes = _override_fonts(docx_bytes)

    mode_label = {'a': '(租賃)', 'b': '(分潤)', 'c': '(固定超額分潤)'}[mode]
    building_id = ctx['building_id']
    party_a = form_data.get('party_a', '').strip()
    filename = f"{building_id}{building_name}-{party_a}-停車場合作協議書-{mode_label}.docx"

    return docx_bytes, filename
