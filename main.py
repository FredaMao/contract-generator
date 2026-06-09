import io
import json
import os
from datetime import datetime
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote
from converter import convert_contract
from generator import generate_contract

app = FastAPI(title="合約系統｜悠勢科技")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

SHEET_ID = '1hirWGvr3H_Rrg3gbtnC_-3vvohB4hTI056PK_admlxg'


def _log_to_sheet(row: list):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if not creds_json:
            return
        creds = Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=['https://www.googleapis.com/auth/spreadsheets'],
        )
        client = gspread.authorize(creds)
        client.open_by_key(SHEET_ID).sheet1.append_row(row)
    except Exception:
        pass


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/convert")
async def convert(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="請上傳 .docx 格式的檔案")
    content = await file.read()
    try:
        output_bytes, output_filename = convert_contract(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"轉換失敗：{str(e)}")
    background_tasks.add_task(_log_to_sheet, [_now(), '轉換器', '', '', '', file.filename])
    encoded_name = quote(output_filename, safe='')
    return StreamingResponse(
        io.BytesIO(output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    company: str = Form(...),
    contract_type: str = Form(...),
    building_id: str = Form(''),
    building_name: str = Form(''),
    building_phone: str = Form(''),
    income_code: str = Form(''),
    party_a: str = Form(''),
    owner: str = Form(''),
    id_number: str = Form(''),
    phone: str = Form(''),
    contact_address: str = Form(''),
    a_email: str = Form(''),
    address: str = Form(''),
    spots: str = Form(''),
    tax_type: str = Form(''),
    bank_name: str = Form(''),
    account_name: str = Form(''),
    account_number: str = Form(''),
    start_date: str = Form(''),
    end_date: str = Form(''),
    sign_date: str = Form(''),
    amount: str = Form(''),
    low_rev: str = Form(''),
    pay_freq: str = Form(''),
    pay_period: str = Form(''),
    pay_day: str = Form(''),
    pay_method: str = Form(''),
    party_a_percent: str = Form(''),
    party_b_percent: str = Form(''),
    sales: str = Form(''),
):
    form_data = {
        'building_id': building_id, 'building_name': building_name,
        'building_phone': building_phone, 'income_code': income_code,
        'party_a': party_a, 'owner': owner, 'id_number': id_number,
        'phone': phone, 'contact_address': contact_address, 'a_email': a_email,
        'address': address, 'spots': spots, 'tax_type': tax_type,
        'bank_name': bank_name, 'account_name': account_name, 'account_number': account_number,
        'start_date': start_date, 'end_date': end_date, 'sign_date': sign_date,
        'amount': amount, 'low_rev': low_rev,
        'pay_freq': pay_freq, 'pay_period': pay_period,
        'pay_day': pay_day, 'pay_method': pay_method,
        'party_a_percent': party_a_percent, 'party_b_percent': party_b_percent,
        'sales': sales,
    }
    try:
        output_bytes, filename = generate_contract(company, contract_type, form_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"產生失敗：{str(e)}")
    type_label = '分潤' if contract_type == 'profit' else '租賃'
    background_tasks.add_task(_log_to_sheet, [
        _now(), '產生器', company, type_label, party_a, building_name, sales,
    ])
    encoded_name = quote(filename, safe='')
    return StreamingResponse(
        io.BytesIO(output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )
