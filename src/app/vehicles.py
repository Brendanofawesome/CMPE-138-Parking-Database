from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from database.establish_db import get_connection


@dataclass(frozen=True, slots=True)
class SavedVehicle:
    licence_value: str
    licence_state: str
    make: str
    model: str
    color: str
    user_id: int

    @property
    def display_name(self) -> str:
        color_prefix = f"{self.color} " if self.color else ""
        return f"{color_prefix}{self.make} {self.model} - {self.licence_value} ({self.licence_state})"


def save_vehicle(
    user_id: int,
    licence_value: str,
    licence_state: str,
    make: str,
    model: str,
    color: str,
) -> bool:
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO vehicle (
                    user_id,
                    color,
                    make,
                    model,
                    Licence_Value,
                    Licence_State
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    color.strip(),
                    make.strip(),
                    model.strip(),
                    licence_value.strip().upper(),
                    licence_state.strip().upper(),
                ),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_saved_vehicles(user_id: int) -> list[SavedVehicle]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT Licence_Value, Licence_State, make, model, color, user_id
            FROM vehicle
            WHERE user_id = ?
            ORDER BY Licence_State, Licence_Value
            """,
            (user_id,),
        ).fetchall()

    return [
        SavedVehicle(
            licence_value=str(row["Licence_Value"]),
            licence_state=str(row["Licence_State"]),
            make=str(row["make"]),
            model=str(row["model"]),
            color=str(row["color"] or ""),
            user_id=int(row["user_id"]),
        )
        for row in rows
    ]


def delete_vehicle(user_id: int, licence_value: str, licence_state: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM vehicle
            WHERE user_id = ?
              AND Licence_Value = ?
              AND Licence_State = ?
            """,
            (user_id, licence_value.strip().upper(), licence_state.strip().upper()),
        )
        conn.commit()
        return cursor.rowcount > 0


def user_owns_vehicle(user_id: int, licence_value: str, licence_state: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM vehicle
            WHERE user_id = ?
              AND Licence_Value = ?
              AND Licence_State = ?
            """,
            (user_id, licence_value.strip().upper(), licence_state.strip().upper()),
        ).fetchone()
    return row is not None
