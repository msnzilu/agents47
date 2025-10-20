from django.db.backends.signals import connection_created
from django.dispatch import receiver

@receiver(connection_created)
def install_pgvector_extension(sender, connection, **kwargs):
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
