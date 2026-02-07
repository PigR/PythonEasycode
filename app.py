from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField
from wtforms.validators import DataRequired, NumberRange
from datetime import datetime
import requests
import os

app = Flask(__name__)
CORS(app)

# Конфигурация
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///currency.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных
db = SQLAlchemy(app)


# Модели
class CurrencyRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    currency_code = db.Column(db.String(10), unique=True, nullable=False)
    rate = db.Column(db.Float, nullable=False)  # Курс к USD
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class UpdateLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    message = db.Column(db.String(200))


# Форма
class ConversionForm(FlaskForm):
    from_currency = StringField('Из валюты', validators=[DataRequired()])
    to_currency = StringField('В валюту', validators=[DataRequired()])
    amount = FloatField('Сумма', validators=[DataRequired(), NumberRange(min=0.01)])


# Создание таблиц
with app.app_context():
    db.create_all()


# Инициализация базы - добавление USD при первом запуске
def initialize_currencies():
    with app.app_context():
        # Добавляем USD, если его нет
        usd = CurrencyRate.query.filter_by(currency_code='USD').first()
        if not usd:
            usd = CurrencyRate(currency_code='USD', rate=1.0)
            db.session.add(usd)
            db.session.commit()
            print("Добавлена валюта USD в базу данных")


# Вызываем инициализацию при старте
initialize_currencies()


# Утилиты
def fetch_exchange_rates():
    """Получение актуальных курсов валют с внешнего API"""
    try:
        # Используем API с поддержкой RUB
        url = 'https://api.exchangerate-api.com/v4/latest/USD'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        update_time = datetime.strptime(data['date'], "%Y-%m-%d")

        # Сохраняем USD (курс 1.0)
        usd_rate = CurrencyRate.query.filter_by(currency_code='USD').first()
        if usd_rate:
            usd_rate.rate = 1.0
            usd_rate.last_updated = update_time
        else:
            usd_rate = CurrencyRate(
                currency_code='USD',
                rate=1.0,
                last_updated=update_time
            )
            db.session.add(usd_rate)

        # Сохраняем другие валюты
        for currency_code, rate in data['rates'].items():
            # Пропускаем USD, так как он уже добавлен
            if currency_code == 'USD':
                continue

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
        log = UpdateLog(success=True, message="Successfully updated exchange rates")
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
        # Приводим коды валют к верхнему регистру
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Если конвертируем из валюты в ту же валюту
        if from_currency == to_currency:
            return round(amount, 2), None

        # Получаем курсы валют к USD
        if from_currency == 'USD':
            from_rate_to_usd = 1.0
        else:
            from_record = CurrencyRate.query.filter_by(currency_code=from_currency).first()
            if not from_record:
                return None, f"Валюта {from_currency} не найдена"
            from_rate_to_usd = from_record.rate

        if to_currency == 'USD':
            to_rate_to_usd = 1.0
        else:
            to_record = CurrencyRate.query.filter_by(currency_code=to_currency).first()
            if not to_record:
                return None, f"Валюта {to_currency} не найдена"
            to_rate_to_usd = to_record.rate

        # Конвертация: через USD как промежуточную валюту
        # 1. Конвертируем исходную валюту в USD
        amount_in_usd = amount / from_rate_to_usd

        # 2. Конвертируем USD в целевую валюту
        converted_amount = amount_in_usd * to_rate_to_usd

        return round(converted_amount, 2), None

    except ZeroDivisionError:
        return None, "Ошибка: деление на ноль"
    except Exception as e:
        return None, f"Ошибка при конвертации: {str(e)}"


# Маршруты
@app.route('/')
def index():
    """Главная страница"""
    form = ConversionForm()
    last_update = get_last_update_time()

    # Получаем список доступных валют
    currencies = CurrencyRate.query.with_entities(CurrencyRate.currency_code).all()
    currency_list = [currency[0] for currency in currencies]

    # Добавляем популярные валюты на первое место
    popular_currencies = ['USD', 'RUB', 'EUR', 'GBP', 'JPY', 'CNY']
    other_currencies = [c for c in currency_list if c not in popular_currencies]
    sorted_currencies = popular_currencies + sorted(other_currencies)

    return render_template('index.html',
                           form=form,
                           last_update=last_update,
                           currencies=sorted_currencies)


@app.route('/api/update_rates', methods=['POST'])
def update_rates():
    """API эндпоинт для обновления курсов валют"""
    success, message = fetch_exchange_rates()

    if success:
        last_update = get_last_update_time()
        return jsonify({
            'success': True,
            'message': message,
            'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else None
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@app.route('/api/last_update', methods=['GET'])
def last_update():
    """API эндпоинт для получения времени последнего обновления"""
    last_update_time = get_last_update_time()

    if last_update_time:
        return jsonify({
            'success': True,
            'last_update': last_update_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Данные еще не обновлялись'
        }), 404


@app.route('/api/convert', methods=['POST'])
def convert():
    """API эндпоинт для конвертации валют"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'message': 'Нет данных'}), 400

    from_currency = data.get('from_currency')
    to_currency = data.get('to_currency')
    amount = data.get('amount')

    # Валидация
    if not all([from_currency, to_currency, amount]):
        return jsonify({'success': False, 'message': 'Все поля обязательны'}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Сумма должна быть положительной'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Некорректная сумма'}), 400

    # Выполняем конвертацию
    result, error = convert_currency(from_currency, to_currency, amount)

    if error:
        return jsonify({'success': False, 'message': error}), 400

    # Добавляем подробную информацию о курсе
    from_record = CurrencyRate.query.filter_by(currency_code=from_currency.upper()).first()
    to_record = CurrencyRate.query.filter_by(currency_code=to_currency.upper()).first()

    rate_info = ""
    if from_record and to_record:
        if from_currency.upper() == 'USD':
            rate = to_record.rate
            rate_info = f"1 USD = {rate:.4f} {to_currency}"
        elif to_currency.upper() == 'USD':
            rate = 1 / from_record.rate
            rate_info = f"1 {from_currency} = {rate:.4f} USD"
        else:
            rate = to_record.rate / from_record.rate
            rate_info = f"1 {from_currency} = {rate:.4f} {to_currency}"

    return jsonify({
        'success': True,
        'result': result,
        'from_currency': from_currency,
        'to_currency': to_currency,
        'amount': amount,
        'rate_info': rate_info
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)