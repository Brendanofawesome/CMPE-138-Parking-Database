from ..establish_db import SQLColumn, Table, register_table


register_table(
    Table(
        name="parking_session",
        columns=(
            SQLColumn(name="session_id", attribute_list="INTEGER PRIMARY KEY AUTOINCREMENT"),
            SQLColumn(name="user_id", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="spot_id", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="status", attribute_list="TEXT NOT NULL DEFAULT 'ON_HOLD'"),
            SQLColumn(name="started_at", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="ended_at", attribute_list="TEXT"),
        ),
        extra_constraints=(
            SQLColumn(name="fk_user_id_users", attribute_list="FOREIGN KEY (user_id) REFERENCES user(user_id)"),
        ),
    )
)
