import requests
from datetime import datetime
from models import CurrencyRate, UpdateLog, db


def fetch_exchange_rates(base_currency='USD'):
    """Получение актуальных курсов валют с внешнего API"""
    try:
        url = f'https://api.exchangerate-api.com/v4/latest/{base_currency}'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Сохраняем курсы в базу данных
        update_time = datetime.strptime(data['date'], "%Y-%m-%d")

        for currency_code, rate in data['rates'].items():
            # Ищем существующую запись или создаем новую
            currency_rate = CurrencyRate.query.filter_by(currency_code=currency_code).first()
            if currency_rate:
                currency_rate.rate = rate
                currency_rate.last_updated = update_time
            else:
                currency_rate = CurrencyRate(
                    currency_code=currency_code,
                    rate=rate,
                    last_updated=update_time
                )
                db.session.add(currency_rate)

        db.session.commit()

        # Логируем успешное обновление
        log = UpdateLog(success=True, message=f"Successfully updated rates for {base_currency}")
        db.session.add(log)
        db.session.commit()

        return True, "Курсы валют успешно обновлены"

    except requests.exceptions.RequestException as e:
        # Логируем ошибку
        log = UpdateLog(success=False, message=str(e))
        db.session.add(log)
        db.session.commit()
        return False, f"Ошибка при получении данных: {str(e)}"


def get_last_update_time():
    """Получение даты и времени последнего обновления"""
    try:
        # Получаем время последнего успешного обновления
        last_update = UpdateLog.query.filter_by(success=True) \
            .order_by(UpdateLog.update_time.desc()) \
            .first()
        if last_update:
            return last_update.update_time
        return None
    except Exception:
        return None


def convert_currency(from_currency, to_currency, amount):
    """Конвертация между валютами"""
    try:
        # Если валюта уже в USD, просто берем ее курс
        if from_currency.upper() == 'USD':
            from_rate = 1.0
        else:
            from_record = CurrencyRate.query.filter_by(currency_code=from_currency.upper()).first()
            if not from_record:
                return None, f"Валюта {from_currency} не найдена"
            from_rate = from_record.rate

        if to_currency.upper() == 'USD':
            to_rate = 1.0
        else:
            to_record = CurrencyRate.query.filter_by(currency_code=to_currency.upper()).first()
            if not to_record:
                return None, f"Валюта {to_currency} не найдена"
            to_rate = to_record.rate

        # Конвертируем: сначала в USD, затем в целевую валюту
        amount_in_usd = amount / from_rate if from_currency.upper() != 'USD' else amount
        converted_amount = amount_in_usd * to_rate if to_currency.upper() != 'USD' else amount_in_usd

        return round(converted_amount, 2), None

    except Exception as e:
        return None, f"Ошибка при конвертации: {str(e)}"