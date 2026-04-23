from pathlib import Path
from app.map.generate_map import generate_map, put_default_lots
from database import establish_db

def initialize_app_data() -> None:
    establish_db.ensure_schema()

    map_data_dir = Path(__file__).resolve().parent / "app" / "map" / "map_data"
    with establish_db.get_connection() as conn:
        put_default_lots(conn)
        generate_map(conn, map_data_dir, "map_base", "final_map")
        conn.commit()

if __name__ == "__main__":
    initialize_app_data()
