from datetime import datetime
from database import db


class CurrencyRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    currency_code = db.Column(db.String(10), unique=True, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Currency {self.currency_code}: {self.rate}>"


class UpdateLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    message = db.Column(db.String(200))