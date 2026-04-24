# CMPE-138-Parking-Database

to debug, run: src/serve_debug.py  
for production, run: gunicorn --chdir src --bind 127.0.0.1:8000 serve_wsgi:app --workers 2 --threads 4