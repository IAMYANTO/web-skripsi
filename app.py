# app.py
from flask import Flask, render_template, request
from models import db, User, AccessLog

app = Flask(__name__)

# Ganti dengan data dari Clever Cloud kamu
# format: mysql+mysqlconnector://USER:PASSWORD@HOST:PORT/DATABASE_NAME
# Pastikan tidak ada spasi di dalam tanda kutip ini
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://ujiqps88uip6czmm:QViN9QYtHk0D1E2eIQUP@brtes9fxxbfuwuurhjfx-mysql.services.clever-cloud.com:3306/brtes9fxxbfuwuurhjfx'

db.init_app(app)

@app.route('/')
def dashboard():
    # Mengambil semua catatan untuk dipajang di web
    logs = AccessLog.query.order_by(AccessLog.waktu.desc()).all()
    return render_template('index.html', logs=logs)

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ini otomatis membuat tabel di Clever Cloud!
    app.run(debug=True)