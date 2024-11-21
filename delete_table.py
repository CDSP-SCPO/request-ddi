from django.db import connection

def drop_all_tables():
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")
        print("Toutes les tables ont été supprimées.")

drop_all_tables()