# CMPE-138-Parking-Database

to debug, run: src/serve_debug.py  
for production, run: gunicorn --chdir src --bind 0.0.0.0:80 serve_wsgi:app --workers 2 --threads 4

database note: `ensure_schema()` adds missing columns but does not rename or drop columns.

view example production deployment!: https://cmpe-138-parking-database.onrender.com/
