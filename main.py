import io
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote
from converter import convert_contract
from generator import generate_contract

app = FastAPI(title="合約系統｜悠勢科技")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="請上傳 .docx 格式的檔案")
    content = await file.read()
    try:
        output_bytes, output_filename = convert_contract(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"轉換失敗：{str(e)}")
    encoded_name = quote(output_filename, safe='')
    return StreamingResponse(
        io.BytesIO(output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@app.post("/generate")
async def generate(
    company: str = Form(...),
    contract_type: str = Form(...),
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
):
    form_data = {
        'party_a': party_a, 'owner': owner, 'id_number': id_number,
        'phone': phone, 'contact_address': contact_address, 'a_email': a_email,
        'address': address, 'spots': spots, 'tax_type': tax_type,
        'bank_name': bank_name, 'account_name': account_name, 'account_number': account_number,
        'start_date': start_date, 'end_date': end_date, 'sign_date': sign_date,
        'amount': amount, 'low_rev': low_rev,
        'pay_freq': pay_freq, 'pay_period': pay_period,
        'pay_day': pay_day, 'pay_method': pay_method,
        'party_a_percent': party_a_percent, 'party_b_percent': party_b_percent,
    }
    try:
        output_bytes, filename = generate_contract(company, contract_type, form_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"產生失敗：{str(e)}")
    encoded_name = quote(filename, safe='')
    return StreamingResponse(
        io.BytesIO(output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )
