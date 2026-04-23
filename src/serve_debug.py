"""Run the application from here :)"""
from db_init import initialize_app_data
from app.flask import create_app
from database.establish_db import get_connection_raw

if __name__ == "__main__":
    initialize_app_data()

    app = create_app(get_connection_raw)

    app.run(debug=True)
