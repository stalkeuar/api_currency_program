from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
import os
import requests
import secrets
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

MONOBANK_API = os.getenv("MONOBANK_API", "https://api.monobank.ua/bank/currency")
INVEST_API_TOKEN = os.getenv("INVEST_API_TOKEN", "")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

app = FastAPI()
security = HTTPBasic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if not AUTH_PASSWORD:
        raise HTTPException(status_code=500, detail="AUTH_PASSWORD не встановлено в .env")
    correct_password = secrets.compare_digest(credentials.password, AUTH_PASSWORD)
    if not correct_password:
        raise HTTPException(
            status_code=401,
            detail="Невірний пароль",
            headers={"WWW-Authenticate": "Basic"}
        )
    return credentials.username

@app.get("/analyze")
def analyze(
    rent: float,
    food: float,
    other: float,
    salary: float,
    username: str = Depends(verify_auth)
):
    expenses = rent + food + other
    savings_uah = salary - expenses

    if savings_uah <= 0:
        raise HTTPException(status_code=400, detail="Немає заощаджень цього місяця")

    try:
        response = requests.get(MONOBANK_API, timeout=5)
        data = response.json()

        if not isinstance(data, list):
            raise ValueError("Очікував список валютних курсів, але отримав щось інше.")

        usd = next((x for x in data if x.get("currencyCodeA") == 840 and x.get("currencyCodeB") == 980), None)

        if not usd:
            raise ValueError("Курс USD/UAH не знайдено в відповіді Monobank")

        rate = usd.get("rateBuy") or usd.get("rateCross")
        if not rate:
            raise ValueError("Немає курсу купівлі або перехресного курсу")

        savings_usd = savings_uah / rate

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Помилка Monobank: {e}")

    def calc_invest(monthly_amount, months=12, annual_rate=0.1):
        monthly_rate = annual_rate / 12
        total = 0
        for _ in range(months):
            total = (total + monthly_amount) * (1 + monthly_rate)
        return total

    try:
        investment_result = calc_invest(savings_usd)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Інвест-API помилка: {e}")

    return JSONResponse({
        "Всього витрачаєте на місяць в грн": round(rent + food + other, 2),
        "Залишок в грн": round(savings_uah, 2),
        "Залишок в доларах США": round(savings_usd, 2),
        "Можливо отримати якщо інвестувати кожен місяць": round(investment_result, 2),
        "Загальний прибуток в доларах": round(investment_result - (savings_usd * 12), 2)
    })
