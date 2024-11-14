from django.db import migrations, models
from django.db.models import F

def convert_text_publisher_to_object(apps, schema_editor):
    # Récupérez les modèles
    Serie = apps.get_model('app', 'Serie')
    Publisher = apps.get_model('app', 'Publisher')

    # Parcourir chaque Série sans publisher associé (ForeignKey vide)
    for serie in Serie.objects.filter(publisher__isnull=True):
        # Créer ou obtenir un Publisher avec le nom actuel de publisher en texte
        publisher_obj, created = Publisher.objects.get_or_create(name=serie.publisher)
        
        # Assigner l'objet Publisher à la Série
        serie.publisher = publisher_obj
        serie.save()

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0012_publisher'),  # Assurez-vous que la dépendance est correcte
    ]

    operations = [
        migrations.RunPython(convert_text_publisher_to_object),
    ]