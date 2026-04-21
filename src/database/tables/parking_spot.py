from ..establish_db import SQLColumn, Table, register_table

###############
# SPOT SCHEMA #
###############
register_table(
    Table(name='parking_spot',
        columns=(
            SQLColumn(name='location_id', attribute_list='NOT NULL'),
            SQLColumn(name='spot_number', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='active', attribute_list='BOOLEAN NOT NULL'),
            SQLColumn(name='location_description', attribute_list='TEXT'),
            SQLColumn(name='type', attribute_list="TEXT NOT NULL"),
            SQLColumn(name='loc_x_min', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='loc_x_max', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='box_y_min', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='box_y_max', attribute_list='INTEGER NOT NULL')
        ),
        extra_constraints=("FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE CASCADE",
                           "PRIMARY KEY (location_id, spot_number)") 
    )
)