from ..establish_db import SQLColumn, Table, register_table


register_table(
    Table(
        name="parking_session",
        columns=(
            SQLColumn(name="session_id", attribute_list="INTEGER PRIMARY KEY AUTOINCREMENT"),
            
            # VEHICLE IDENTIFICATION (by plate)
            SQLColumn(name="Licence_Value", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="Licence_State", attribute_list="TEXT NOT NULL"),
            
            SQLColumn(name="user_id", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="location_id", attribute_list="INTEGER"),
            SQLColumn(name="spot_id", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="Licence_Value", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="Licence_State", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="status", attribute_list="TEXT"),
            SQLColumn(name="started_at", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="ended_at", attribute_list="TEXT"),
        ),
        extra_constraints=(
            SQLColumn(
                name="fk_fee_vehicle",
                attribute_list="""
                FOREIGN KEY (Licence_Value, Licence_State)
                REFERENCES vehicle(Licence_Value, Licence_State)
                ON DELETE CASCADE
                """,
            ),
            SQLColumn(name="fk_user_id_users", attribute_list="FOREIGN KEY (user_id) REFERENCES user(user_id)"),
            SQLColumn(name="fk_session_vehicle", attribute_list="FOREIGN KEY (Licence_Value, Licence_State) REFERENCES vehicle(Licence_Value, Licence_State)"),
        ),
    )
)

