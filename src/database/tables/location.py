from ..establish_db import SQLColumn, Table, register_table

###################
# LOCATION SCHEMA #
###################
register_table(
    Table(name='location',
        columns=(
            SQLColumn(name="location_id", attribute_list="INTEGER PRIMARY KEY AUTOINCREMENT"),
            SQLColumn(name="lot_name", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="manager", attribute_list=""),
            SQLColumn(name="manager_contact", attribute_list="TEXT"),
            SQLColumn(name="hourly_cost_cents", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="x_coordinate", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="y_coordinate", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="data_name", attribute_list="TEXT NOT NULL UNIQUE")
        ),
        extra_constraints=(
            SQLColumn(name="fk_location_manager", attribute_list="FOREIGN KEY (manager) REFERENCES user(user_id)"),
        )
    )
)
