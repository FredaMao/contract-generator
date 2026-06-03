import io
import os
import re
import zipfile
from docxtpl import DocxTemplate

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


def generate_contract(company_key: str, contract_type: str, form_data: dict) -> tuple[bytes, str]:
    station_name = form_data.get('station_name', '').strip()
    if not station_name:
        raise ValueError('場站名稱為必填欄位')

    ctx = dict(form_data)

    for field in ('start_date', 'end_date', 'sign_date'):
        ctx[field] = date_to_minguo(ctx.get(field, ''))

    ctx['email'] = ctx.get('a_email', '')

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
    docx_bytes = _override_fonts(buf.getvalue())

    type_label = '租賃' if contract_type == 'rent' else '分潤'
    station_id = form_data.get('station_id', '').strip()
    party_a = form_data.get('party_a', '').strip()
    bracket = f"[{station_id}{station_name}]"
    filename = f"{bracket}-{party_a}-{type_label}合約.docx"

    return docx_bytes, filename
