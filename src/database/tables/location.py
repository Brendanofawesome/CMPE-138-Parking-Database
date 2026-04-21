from ..establish_db import SQLColumn, Table, register_table

###################
# LOCATION SCHEMA #
###################
register_table(
    Table(name='location',
        columns=(
            SQLColumn(name="location_id", attribute_list="INTEGER PRIMARY KEY AUTOINCREMENT"),
            SQLColumn(name="x_coordinate", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="y_coordinate", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="lot_name", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="manager", attribute_list=""),
            SQLColumn(name="manager_contact", attribute_list="TEXT"),
            SQLColumn(name="cost_cents", attribute_list="INTEGER NOT NULL"),   
            SQLColumn(name="spots", attribute_list="AS (SELECT COUNT(*) FROM parking_spot WHERE parking_spot.location_id = location_id)"),
            SQLColumn(name="dataname", attribute_list="TEXT NOT NULL UNIQUE")
        ),
        extra_constraints=("FOREIGN KEY (manager) REFERENCES user(user_id)",)
    )
)