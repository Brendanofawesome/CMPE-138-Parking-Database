from flask_squeeze import Squeeze
from app.flask import create_app
from database import establish_db

squeeze = Squeeze()
app = create_app(establish_db.get_connection_raw)
squeeze.init_app(app)
