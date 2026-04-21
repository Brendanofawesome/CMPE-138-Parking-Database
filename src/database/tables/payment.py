from ..establish_db import SQLColumn, Table, register_table


register_table(
    Table(
        name="payment",
        columns=(
            SQLColumn(name="payment_id", attribute_list="INTEGER PRIMARY KEY AUTOINCREMENT"),
            SQLColumn(name="fee_id", attribute_list="INTEGER NOT NULL"),
            SQLColumn(name="method", attribute_list="TEXT NOT NULL"),
            SQLColumn(name="amount", attribute_list="REAL NOT NULL CHECK(amount >= 0)"),
            SQLColumn(name="paid_at", attribute_list="TEXT NOT NULL"),
        ),
        extra_constraints=(
            "FOREIGN KEY (fee_id) REFERENCES fee(fee_id)",
        ),
    )
)
