from ..establish_db import SQLColumn, Table, register_table

###############
# FEE SCHEMA #
###############
register_table(
    Table(
        name="fee",
        columns=(
            SQLColumn(name="fee_id", attribute_list="INTEGER PRIMARY KEY AUTOINCREMENT"),

            SQLColumn(name="user_id", attribute_list="INTEGER NOT NULL"),

            SQLColumn(name="parent_fee_id", attribute_list="INTEGER"),
            SQLColumn(name="session_id", attribute_list="INTEGER"),
        
            SQLColumn(name="created_at", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="valid_until", attribute_list="INTEGER NOT NULL"),

            SQLColumn(name="amount", attribute_list="DOUBLE NOT NULL"),
            SQLColumn(name="description", attribute_list="TEXT"),
            SQLColumn(name="fee_type", attribute_list="TEXT NOT NULL"),
        ),
        extra_constraints=(
            SQLColumn(
                name="fk_fee_user",
                attribute_list="FOREIGN KEY (user_id) REFERENCES user(user_id)",
            ),
            SQLColumn(
                name="fk_fee_session",
                attribute_list="FOREIGN KEY (session_id) REFERENCES parking_session(session_id)",
            ),
            SQLColumn(
                name="fk_fee_parent_fee",
                attribute_list="FOREIGN KEY (parent_fee_id) REFERENCES fee(fee_id) ON DELETE SET NULL",
            ),
        ),
    )
)