# -- DJANGO
from django.core.management.base import BaseCommand

# -- BASEDEQUESTIONS
from app.models import (
    BindingConcept, BindingSurveyRepresentedVariable, Category, Collection,
    Concept, ConceptualVariable, Distributor, RepresentedVariable,
    Subcollection, Survey,
)


class Command(BaseCommand):
    help = 'Supprime toutes les données de la base de données dans un ordre spécifique'

    def handle(self, *args, **kwargs):
        # Supprimer les données dans l'ordre correct pour éviter les problèmes de dépendances
        BindingConcept.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted BindingConcept'))

        BindingSurveyRepresentedVariable.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted BindingSurveyRepresentedVariable'))

        Category.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted Category'))

        Concept.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted Concept'))

        RepresentedVariable.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted RepresentedVariable'))

        ConceptualVariable.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted ConceptualVariable'))

        Survey.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted Survey'))

        Subcollection.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted Subcollection'))

        Collection.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted Collection'))

        Distributor.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Deleted Distributor'))

        self.stdout.write(self.style.SUCCESS('All data cleared successfully!'))
