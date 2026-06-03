import io
import os
from docxtpl import DocxTemplate

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

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '自動產生合約範本')


def generate_contract(company_key: str, contract_type: str, form_data: dict) -> tuple[bytes, str]:
    co = COMPANIES.get(company_key)
    if not co:
        raise ValueError(f'未知的公司：{company_key}')

    if contract_type == 'rent':
        tpl_file = 'template_rent.docx'
    elif contract_type == 'profit':
        tpl_file = 'template_profit.docx'
    else:
        raise ValueError(f'未知的合約類型：{contract_type}')

    tpl = DocxTemplate(os.path.join(TEMPLATE_DIR, tpl_file))

    ctx = dict(form_data)
    # Auto-fill 乙方 (management company) fields from company profile
    ctx['party_b'] = co['name']
    ctx['b_owner'] = co['owner']
    ctx['b_id'] = co['id']
    ctx['b_phone'] = co['phone']
    ctx['b_address'] = co['address']
    ctx['b_email'] = co['email']

    tpl.render(ctx)

    buf = io.BytesIO()
    tpl.save(buf)

    type_label = '租賃' if contract_type == 'rent' else '分潤'
    addr = form_data.get('address', '').strip()[:12]
    filename = f"{co['name']}_{type_label}合約_{addr}.docx"

    return buf.getvalue(), filename
