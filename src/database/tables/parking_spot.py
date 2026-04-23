from ..establish_db import SQLColumn, Table, register_table

###############
# SPOT SCHEMA #
###############
register_table(
    Table(name='parking_spot',
        columns=(
            SQLColumn(name='location_id', attribute_list='NOT NULL'),
            SQLColumn(name='spot_id', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='active', attribute_list='BOOLEAN NOT NULL'),
            SQLColumn(name='location_description', attribute_list='TEXT'),
            SQLColumn(name='type', attribute_list="TEXT NOT NULL"),
            SQLColumn(name='box_x_min', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='box_x_max', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='box_y_min', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='box_y_max', attribute_list='INTEGER NOT NULL')
        ),
        primary_key=('location_id', 'spot_id'),
        extra_constraints=(
            SQLColumn(name='fk_parking_spot_location', attribute_list='FOREIGN KEY (location_id) REFERENCES location(location_id) ON DELETE CASCADE'),
        )
    )
)