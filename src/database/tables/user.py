from ..establish_db import SQLColumn, Table, register_table

###############
# USER SCHEMA #
###############
register_table(
    Table(name='user', 
        columns=(
            SQLColumn(name='user_id', attribute_list='INTEGER PRIMARY KEY AUTOINCREMENT'),
            SQLColumn(name='username', attribute_list='TEXT NOT NULL UNIQUE'),
            SQLColumn(name='password_hash', attribute_list='BLOB NOT NULL'),
            SQLColumn(name='hash_algorithm', attribute_list='TEXT NOT NULL'),
            SQLColumn(name='salt', attribute_list='BLOB NOT NULL'),
            SQLColumn(name='phone_number', attribute_list='TEXT NOT NULL')
        )
    )
)

########################################
# Session Token Multi-Valued Attribute #
########################################

register_table(
    Table(name='session tokens',
          columns=(
              SQLColumn(name='token_id', attribute_list='INTEGER PRIMARY KEY AUTOINCREMENT'),
              
              SQLColumn(name='user_id', attribute_list="INTEGER NOT NULL"),
              SQLColumn(name='session_id_hash', attribute_list='BLOB NOT NULL UNIQUE'),
              
              SQLColumn(name='expires_at', attribute_list='INTEGER NOT NULL')
          ),
          extra_constraints=("FOREIGN KEY (user_id) REFERENCES users(user_id)",)
    )
)