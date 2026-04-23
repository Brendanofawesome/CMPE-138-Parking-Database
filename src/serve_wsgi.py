from app.flask import create_app
from database import establish_db

app = create_app(establish_db.get_connection_raw)
