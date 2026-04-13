"""Run the application from here :)"""

from app.flask import create_app
from database import establish_db

if __name__ == "__main__":
    establish_db.ensure_schema()
    
    app = create_app(establish_db.get_connection_raw)
    
    app.run(debug=True)