from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import httpx
from typing import Optional

app = FastAPI()
security = HTTPBasic()

PASSWORD = "dfjgidf5346sggwefrk###gjgkidfjkd"

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.password != PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

@app.get("/calculate")
async def calculate_price(
    item_name: str,
    item_price_usd: float,
    savings_uah: float,
    authenticated: bool = Depends(authenticate)
):

    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.monobank.ua/bank/currency")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Помилка отримання курсу валют з Monobank")
        rates = response.json()

    usd_uah_rate = None
    for rate in rates:
        if rate["currencyCodeA"] == 840 and rate["currencyCodeB"] == 980:
            usd_uah_rate = rate["rateSell"]
            break

    if not usd_uah_rate:
        raise HTTPException(status_code=500, detail="Не знайдено курс долара до гривні")

    savings_usd = savings_uah / usd_uah_rate
    diff = item_price_usd - savings_usd

    if diff <= 0:
        message = f"Вітаємо! Ви вже можете придбати '{item_name}' 🥳"
    elif diff < 100:
        message = f"Ще трішки попрацювати — і '{item_name}' буде вашим!"
    elif diff < 1000:
        message = f"Працювати ще багатенько, але не слід засмучуватись — '{item_name}' нікуди не втече!"
    else:
        message = f"Треба шукати нову роботу 😅 До '{item_name}' ще далеко..."

    return {
        "Назва товару": item_name,
        "Курс USD": round(usd_uah_rate, 2),
        "Ваші накопичення в доларах": round(savings_usd, 2),
        "Ціна товару в доларах": item_price_usd,
        "Скільки ще треба накопичити": round(max(diff, 0), 2),
        "Повідомлення": message
    }

