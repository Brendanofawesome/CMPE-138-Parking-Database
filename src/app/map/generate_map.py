from typing import NamedTuple
from pathlib import Path

import sqlite3
from PIL import Image
from pandas import DataFrame, read_csv

class LotDataInfo(NamedTuple):
    location_id: int
    x_coordinate: int
    y_coordinate: int
    data_name: str  # needs to match filename

def get_lot_data_info(connection: sqlite3.Connection) -> tuple[LotDataInfo, ...]:
    if not connection:
        return ()
    
    rows = connection.execute("SELECT location_id, x_coordinate, y_coordinate, data_name FROM location").fetchall()
    
    return tuple(LotDataInfo(row["location_id"], row["x_coordinate"], row["y_coordinate"], row["data_name"]) for row in rows)

def get_lot_data(filepath: Path, data_info: LotDataInfo) -> tuple[Image.Image, DataFrame]:
    root_path = filepath.resolve()
    safe_file_path = (root_path / data_info.data_name).resolve()
    
    if not safe_file_path.is_relative_to(root_path):
        raise ValueError("Invalid data name")
    
    #grab the image file
    try:
        image = Image.open(safe_file_path.with_suffix(".png"))
    except Exception as exc:
        raise FileExistsError(f"lot image file could not be opened: {data_info.data_name}") from exc
        
    #grab the spot metadata
    try:
        spot_data = read_csv(safe_file_path.with_suffix(".csv"))
    except Exception as exc:
        raise FileExistsError(f"lot spot file could not be opened: {data_info.data_name}") from exc
    
    #ensure spot data has exactly the expected columns
    expected_columns = {"spot_id", "spot_type", "start_x", "end_x", "start_y", "end_y"}
    if set(spot_data.columns) != expected_columns:
        raise ValueError(f"lot spot file has incorrect columns: {data_info.data_name}")
        
    #ensure datatypes are correct
    if not all(spot_data.dtypes[col] == "int64" for col in ["start_x", "end_x", "start_y", "end_y"]):
        raise ValueError(f"lot spot file has incorrect datatypes: {data_info.data_name}")
    
    return (image, spot_data)

#puts the lot image onto the map image in the requested position and updates coordinates in spot_data
def put_lot_image_on_map(map_image: Image.Image, lot_image: Image.Image, lot_data: LotDataInfo, spot_data: DataFrame) -> None:
    paste_position = (lot_data.x_coordinate, lot_data.y_coordinate)

    #only provide a mask when the lot image actually carries transparency.
    if "A" in lot_image.getbands():
        map_image.paste(lot_image, paste_position, lot_image.getchannel("A"))
    elif lot_image.mode == "P" and "transparency" in lot_image.info:
        lot_image_rgba = lot_image.convert("RGBA")
        map_image.paste(lot_image_rgba, paste_position, lot_image_rgba.getchannel("A"))
    else:
        map_image.paste(lot_image, paste_position)
    
    spot_data["start_x"] += lot_data.x_coordinate
    spot_data["end_x"] += lot_data.x_coordinate + 1
    spot_data["start_y"] += lot_data.y_coordinate
    spot_data["end_y"] += lot_data.y_coordinate + 1
    
def put_spots_in_db(connection: sqlite3.Connection, lot_data: LotDataInfo, spot_data: DataFrame) -> None:
    for _, row in spot_data.iterrows():
        connection.execute(
            """
            INSERT INTO parking_spot (location_id, spot_id, active, location_description, type, box_x_min, box_x_max, box_y_min, box_y_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(location_id, spot_id) DO UPDATE SET
                active=excluded.active,
                location_description=excluded.location_description,
                type=excluded.type,
                box_x_min=excluded.box_x_min,
                box_x_max=excluded.box_x_max,
                box_y_min=excluded.box_y_min,
                box_y_max=excluded.box_y_max
            """,
            (
                lot_data.location_id,
                row["spot_id"],
                True,
                "",
                row["spot_type"],
                row["start_x"],
                row["end_x"],
                row["start_y"],
                row["end_y"]
            )
        )
    
def generate_map(connection: sqlite3.Connection, lot_filepath: Path, base_map_name: str, final_map_name: str) -> None:
    lot_data_infos = get_lot_data_info(connection)
    root_path = lot_filepath.resolve()
    
    #initialize the map image
    base_map_path = (root_path / base_map_name).resolve()
    if not base_map_path.is_relative_to(root_path):
        raise ValueError("Invalid base map name")
    
    try:
        map_image = Image.open(base_map_path.with_suffix(".bmp"))
    except Exception as exc:
        raise FileExistsError(f"base map file could not be opened: {base_map_name}.bmp") from exc
    
    for lot_info in lot_data_infos:
        #put each lot on the map
        lot_image, spot_data = get_lot_data(lot_filepath, lot_info)
        put_lot_image_on_map(map_image, lot_image, lot_info, spot_data)
        
        #put each spot into the database
        put_spots_in_db(connection, lot_info, spot_data)
        
    #save the final map image
    final_map_path = (root_path / final_map_name).resolve()
    if not final_map_path.is_relative_to(root_path):
        raise ValueError("Invalid final map name")
    
    try:
        map_image.save(final_map_path.with_suffix(".png"))
    except Exception as exc:
        raise FileExistsError(f"final map file could not be saved: {final_map_name}.png") from exc
    
def put_default_lots(connection: sqlite3.Connection) -> None:
    lots: tuple[LotDataInfo, ...] = (
        LotDataInfo(1, 404, 242, "lot1"),
        LotDataInfo(2, 1000, 742, "lot2"),
        LotDataInfo(3, 284, 1100, "lot3"),
    )
    
    for lot in lots:
        connection.execute(
            """
            INSERT INTO location (lot_name, manager, manager_contact, hourly_cost_cents, x_coordinate, y_coordinate, data_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(data_name) DO UPDATE SET
                lot_name=excluded.lot_name,
                manager=excluded.manager,
                manager_contact=excluded.manager_contact,
                hourly_cost_cents=excluded.hourly_cost_cents,
                x_coordinate=excluded.x_coordinate,
                y_coordinate=excluded.y_coordinate
            """,
            (
                f"Lot {lot.location_id}",
                None,
                None,
                500,
                lot.x_coordinate,
                lot.y_coordinate,
                lot.data_name
            )
        )
    
    
if __name__ == "__main__":
    import sys # pylint: disable=import-outside-toplevel
    SRC_PATH = str(Path(__file__).resolve().parents[2])
    if SRC_PATH not in sys.path:
        sys.path.append(SRC_PATH)
    
    from database.establish_db import get_connection, ensure_schema # pylint: disable=import-error
    ensure_schema()
    
    with get_connection() as test_conn:
        put_default_lots(test_conn)
        generate_map(test_conn, Path(__file__).resolve().parent / "map_data", "map_base", "final_map")
