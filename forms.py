from flask_wtf import FlaskForm
from wtforms import StringField, FloatField
from wtforms.validators import DataRequired, NumberRange

class ConversionForm(FlaskForm):
    from_currency = StringField('Из валюты', validators=[DataRequired()])
    to_currency = StringField('В валюту', validators=[DataRequired()])
    amount = FloatField('Сумма', validators=[DataRequired(), NumberRange(min=0.01)])