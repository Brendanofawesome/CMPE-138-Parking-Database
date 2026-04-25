from ..establish_db import SQLColumn, Table, register_table

register_table(
    Table(name='vehicle', 
        columns=(
            SQLColumn(name='License_Value', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='License_State', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='Make', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='Color', attribute_list='TEXT'),
            SQLColumn(name='Model', attribute_list='TEXT NOT NULL'),
            SQLColumn(name="user_id", attribute_list="INTEGER NOT NULL")
        ),
        primary_key=("License_Value", "License_State", "user_id"),
        extra_constraints=(
            SQLColumn(name='fk_vehicle_user', attribute_list='FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE'),
        )
    )
)
