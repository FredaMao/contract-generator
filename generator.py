import io
import os
import random
import re
import zipfile
from docxtpl import DocxTemplate
from converter import xml_escape, list_paragraphs

FONT = '微軟正黑體'

COMPANIES = {
    '志昌': {
        'name': '志昌資產管理有限公司',
        'owner': '謝昌志',
        'id': '90634048',
        'phone': '0917-444-186',
        'address': '臺北市中山區長安東路2段80號10樓之1',
        'email': '',
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

COMPANY_TEMPLATES = {'rent': 'template_rent.docx', 'profit': 'template_profit.docx'}
USPACE_TEMPLATES = {'rent': 'template_rent_uspace.docx', 'profit': 'template_profit_uspace.docx'}

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '自動產生合約範本')


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
    targets = {'word/document.xml', 'word/styles.xml'}
    with zipfile.ZipFile(in_buf) as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename in targets:
                    data = _apply_font_xml(data.decode('utf-8')).encode('utf-8')
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
    if not padding:
        return xml
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
        if not padding:
            continue
        para_xml = xml[ps:pe]
        if '<w:sdt>' in para_xml or '<w:sdt ' in para_xml:
            xml = _inject_padding_into_para_sdt(xml, ps, pe, padding, sfx)
        else:
            xml = _rebuild_para_text(xml, ps, pe, pre + padding + sfx)
    return xml


def _apply_date_format(xml: str, sign_date: str = '') -> str:
    """Set signing date line to font size 20; inject sign_date when provided."""
    DATE_TEXT = '中　華　民　國　　　年　　月　　日'
    paragraphs = list_paragraphs(xml)
    total = len(paragraphs)
    for i, (ps, pe, text) in enumerate(paragraphs):
        if i < total // 2:
            continue
        if _DATE_PAT.search(text) and '法規' not in text and '法律' not in text:
            if re.search(r'\d', text):
                new_text = text
            elif sign_date:
                new_text = '中　華　民　國　' + sign_date
            else:
                para_xml = xml[ps:pe]
                if '<w:sdt>' in para_xml or '<w:sdt ' in para_xml:
                    break  # uspace template already formatted correctly, leave intact
                new_text = DATE_TEXT
            xml = _rebuild_para_text(xml, ps, pe, new_text, size=20)
            break
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
                    data = doc_xml.encode('utf-8')
                elif item.filename.startswith('word/') and item.filename.endswith('.xml'):
                    xml_str = data.decode('utf-8')
                    if 'w14:paraId' in xml_str or 'w14:textId' in xml_str:
                        xml_str = _fix_paragraph_ids(xml_str)
                        data = xml_str.encode('utf-8')
                zout.writestr(item, data)
    return out_buf.getvalue()


def generate_contract(company_key: str, contract_type: str, form_data: dict) -> tuple[bytes, str]:
    building_name = form_data.get('building_name', '').strip()
    if not building_name:
        raise ValueError('建物名稱為必填欄位')

    ctx = dict(form_data)

    for field in ('start_date', 'end_date', 'sign_date'):
        ctx[field] = date_to_minguo(ctx.get(field, ''))

    ctx['email'] = ctx.get('a_email', '')

    contract_prefix = '分潤' if contract_type == 'profit' else '租賃'
    tax_str = form_data.get('tax_type', '')
    ctx['contract_tax_label'] = f"{contract_prefix}{tax_str}/手續費內含"
    ctx['building_id'] = form_data.get('building_id', '').strip()
    ctx['building_name'] = building_name
    ctx['building_phone'] = form_data.get('building_phone', '').strip()
    # income_code value encodes category + code, e.g. "個人_空地租賃(51L)"
    ic_full = form_data.get('income_code', '').strip()
    ic_display = ic_full.split('_', 1)[1] if '_' in ic_full else ic_full
    ctx['income_code'] = ic_display
    ctx['ic_personal_51L']   = (ic_full == '個人_空地租賃(51L)')
    ctx['ic_personal_51J']   = (ic_full == '個人_建物租賃(51J)')
    ctx['ic_corp_00']        = (ic_full == '法人_00發票')
    ctx['ic_committee_51L']  = (ic_full == '管委會_空地租賃(51L)')
    ctx['ic_committee_51J']  = (ic_full == '管委會_建物租賃(51J)')
    ctx['ic_committee_00']   = (ic_full == '管委會_00發票')
    ctx['sales'] = form_data.get('sales', '').strip()

    if company_key == '悠勢':
        tpl_file = USPACE_TEMPLATES.get(contract_type)
        if not tpl_file:
            raise ValueError(f'未知的合約類型：{contract_type}')
        ctx['email'] = ctx.get('a_email', '')
        company_label = '悠勢科技'
    else:
        co = COMPANIES.get(company_key)
        if not co:
            raise ValueError(f'未知的公司：{company_key}')
        tpl_file = COMPANY_TEMPLATES.get(contract_type)
        if not tpl_file:
            raise ValueError(f'未知的合約類型：{contract_type}')
        ctx['party_b'] = co['name']
        ctx['b_owner'] = co['owner']
        ctx['b_id'] = co['id']
        ctx['b_phone'] = co['phone']
        ctx['b_address'] = co['address']
        ctx['b_email'] = co['email']
        company_label = co['name']

    tpl = DocxTemplate(os.path.join(TEMPLATE_DIR, tpl_file))
    tpl.render(ctx)

    buf = io.BytesIO()
    tpl.save(buf)
    docx_bytes = _post_process_docx(buf.getvalue(), ctx.get('sign_date', ''))
    docx_bytes = _override_fonts(docx_bytes)

    contract_title = '停車位租賃契約書' if contract_type == 'rent' else '停車位服務契約書'
    building_id = ctx['building_id']
    party_a = form_data.get('party_a', '').strip()
    bracket = f"[{building_id}{building_name}]"
    filename = f"{bracket}-{party_a}-{contract_title}.docx"

    return docx_bytes, filename
