import logging
import requests
from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
CURRENCY_CHOICES = {'USD': 840, 'EUR': 978, 'RUB': 643}
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_time = db.Column(db.String, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    shop_order_id = db.Column(db.Integer, nullable=False)


@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == "POST":
        try:
            if request.form['currency'] == 'EUR':
                return pay(request)
            elif request.form['currency'] == 'USD':
                return piastix(request)
            elif request.form['currency'] == 'RUB':
                return invoice(request)
        except (ValueError, RuntimeError) as err:
            return render_template('error.html', error=err)
    return render_template('index.html')


def pay(req):
    method_used('Pay')
    data = get_data(req)
    save_to_db(data)
    data['shop_id'] = req.form['shop_id']
    data['secret'] = req.form['secret']
    link = f"{data['amount']}:{data['currency']}:{data['shop_id']}:{data['shop_order_id']}{data['secret']}"
    hash_code = hashlib.sha256(link.encode('utf-8')).hexdigest()
    data['sign'] = hash_code
    return render_template('pay.html', data=data)


def piastix(req):
    method_used('Piastix')
    api_url = "https://core.piastrix.com/bill/create"
    data = get_data(req)
    data['shop_id'] = req.form['shop_id']
    data['secret'] = req.form['secret']
    json = {
        "description": data['description'],
        "payer_currency": data['currency'],
        "shop_amount": data['amount'],
        "shop_currency": data['currency'],
        "shop_id": data['shop_id'],
        "shop_order_id": data['shop_order_id'],
    }
    link = f"{json['payer_currency']}:{json['shop_amount']}:" \
           f"{json['shop_currency']}:{json['shop_id']}:{json['shop_order_id']}{data['secret']}"
    hash_code = hashlib.sha256(link.encode('utf-8')).hexdigest()
    json['sign'] = hash_code
    r = requests.post(url=api_url, json=json)
    if r.status_code == 200:
        save_to_db(data)
        payment_url = r.json()['data']['url']
        logging.info(f'Response was received. Status code: {r.status_code}')
        return redirect(payment_url, code=302)
    logging.error(f'Error. Invalid response. Status code: {r.status_code}')
    raise RuntimeError('Failed. Please try again later')


def invoice(req):
    method_used('Invoice')
    api_url = "https://core.piastrix.com/invoice/create"
    data = get_data(req)
    data['shop_id'] = req.form['shop_id']
    data['secret'] = req.form['secret']
    json = {
        "description": data['description'],
        "currency": data['currency'],
        "amount": data['amount'],
        "shop_id": data['shop_id'],
        "shop_order_id": data['shop_order_id'],
        "payway": "advcash_rub",
    }
    link = f"{json['amount']}:{json['currency']}:" \
           f"{json['payway']}:{json['shop_id']}:{json['shop_order_id']}{data['secret']}"
    hash_code = hashlib.sha256(link.encode('utf-8')).hexdigest()
    json['sign'] = hash_code
    r = requests.post(url=api_url, json=json)
    if r.status_code == 200:
        save_to_db(data)
        data = r.json()['data']
        logging.info(f'Response was received. Status code: {r.status_code}')
        return render_template('invoice.html', data=data)
    logging.error(f'Error. Invalid response. Status code: {r.status_code}')
    raise RuntimeError('Failed. Please try again later')


def save_to_db(data):
    amount_in_cents = int(float(data["amount"])*100)
    validate_amount(amount_in_cents)
    order = Order(payment_time=data["payment_time"],
                  amount=amount_in_cents,
                  currency=data["currency"],
                  description=data["description"],
                  shop_order_id=data["shop_order_id"]
                  )
    try:
        db.session.add(order)
        db.session.commit()
        logging.info('Order was successfully saved to DB')
    except:
        logging.error('Error. Order was not saved to DB')


def get_data(req):
    return {
        "payment_time": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        "amount": req.form['amount'],
        "currency": CURRENCY_CHOICES[req.form['currency']],
        "description": req.form['description'],
        "shop_order_id": req.form['shop_order_id']
    }


def method_used(method):
    logging.info(f'{method} method is used.')


def validate_amount(cents):
    if type(cents) != int:
        logging.error('Incorrect amount type. Should be an integer values')
        raise ValueError("Incorrect amount type. Should be an integer values")
    elif cents < 0:
        logging.error('Amount should be positives')
        raise ValueError("Amount should be positive")


if __name__ == '__main__':
    app.run()
