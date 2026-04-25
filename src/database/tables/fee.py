from ..establish_db import SQLColumn, Table, register_table


register_table(
    Table(
        name="fee",
        columns=(
            SQLColumn(name="fee_id", attribute_list="INTEGER PRIMARY KEY AUTOINCREMENT"),
            SQLColumn(name="user_id", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="session_id", attribute_list="INTEGER"),
            SQLColumn(name="description", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="cost", attribute_list="REAL NOT NULL CHECK(cost >= 0)"),
            SQLColumn(name="status", attribute_list="TEXT NOT NULL DEFAULT 'UNPAID'"),
            SQLColumn(name="valid_until", attribute_list="TEXT"),
            SQLColumn(name="created_at", attribute_list="TEXT NOT NULL"),
        ),
        extra_constraints=(
            SQLColumn(name="fk_fee_user", attribute_list="FOREIGN KEY (user_id) REFERENCES user(user_id)"),
            SQLColumn(name="fk_fee_session", attribute_list="FOREIGN KEY (session_id) REFERENCES parking_session(session_id)"),
        ),
    )
)
