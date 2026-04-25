from ..establish_db import SQLColumn, Table, register_table

###############
# FEE SCHEMA #
###############
register_table(
    Table(name='fee',
        columns=(
            SQLColumn(name='fee_id', attribute_list='INTEGER PRIMARY KEY AUTOINCREMENT'),
            SQLColumn(name='vehicle_id', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='user_id', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='payment_id', attribute_list='INTEGER'),
            SQLColumn(name='parent_fee_id', attribute_list='INTEGER'), #for penalty fee chaining
            SQLColumn(name='created_at', attribute_list='INTEGER NOT NULL'), #renamed from 'timestamp'
            SQLColumn(name='valid_until', attribute_list='INTEGER NOT NULL'),
            SQLColumn(name='amount', attribute_list='DOUBLE NOT NULL'),
            SQLColumn(name='description', attribute_list='TEXT'), #might not be needed
            SQLColumn(name='fee_type', attribute_list='TEXT NOT NULL') #regular session, penalty, 
        ),
        extra_constraints=(
            SQLColumn(name='fk_fee_vehicle', attribute_list='FOREIGN KEY (vehicle_id) REFERENCES vehicle(vehicle_id) ON DELETE CASCADE'),
            SQLColumn(name='fk_fee_user', attribute_list='FOREIGN KEY (user_id) REFERENCES user(user_id)'),
            SQLColumn(name='fk_fee_payment', attribute_list='FOREIGN KEY (payment_id) REFERENCES payment(payment_id) ON DELETE SET NULL'),
            SQLColumn(name='fk_fee_parent_fee', attribute_list='FOREIGN KEY (parent_fee_id) REFERENCES fee(fee_id) ON DELETE SET NULL')
        )
    )
)
