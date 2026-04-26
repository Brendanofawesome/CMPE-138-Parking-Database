from ..establish_db import SQLColumn, Table, register_table

##################
# VEHICLE SCHEMA #
##################

register_table(
    Table(
        name='vehicle',
        columns=(
            SQLColumn(name='user_id', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='color', attribute_list='TEXT'),
            SQLColumn(name='make', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='model', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='license_plate_value', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='license_plate_state', attribute_list='TEXT NOT NULL')
        ),
        primary_key=("license_plate_value", "license_plate_state"),

        extra_constraints=(
            SQLColumn(name='fk_vehicle_user', attribute_list='FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE'),
        )
    )
)