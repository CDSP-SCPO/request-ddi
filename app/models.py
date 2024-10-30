# -- DJANGO
from django.db import models

# class Entites(models.Model):
#     orcid
#     name
#     affiliation

class Serie(models.Model):
    name = models.CharField()
    publisher = models.CharField()
    abstract = models.TextField()
    photo = models.ImageField(upload_to='series_photos/', blank=True, null=True)

    def __str__(self):
        return f"{self.name}"

class Survey(models.Model):
    # auteur
    # producteur
    # date de prod
    # pays
    # unite geographique
    # unite d analyse
    # methode temporel
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE, null=True)
    external_ref = models.CharField(max_length=255)
    name = models.TextField()

    def __str__(self):
        return f"Survey: {self.name} ({self.external_ref})"

class ConceptualVariable(models.Model):
    internal_label = models.TextField()
    concepts = models.ManyToManyField("Concept", symmetrical=False, related_name="conceptual_variables")

    def __str__(self):
        # Récupérer toutes les variables représentées associées
        represented_vars = self.representedvariable_set.all()

        # Si au moins une variable représentée existe, on l'affiche
        if represented_vars.exists():
            return f"Conceptual Variable: {self.internal_label}, Linked Represented Variables: {', '.join([str(var.internal_label) for var in represented_vars])}"
        else:
            return f"Conceptual Variable: {self.internal_label} (No linked represented variables)"



class Category(models.Model):
    """careful when editing a category, most of the time we should be creating a new one instead"""
    code = models.CharField(max_length=255)  # code if type code, else conditions / limitation ?
    category_label = models.TextField(null=True)  # pas de label si pas type==code?

    def __str__(self):
        return f"{self.code} : {self.category_label}"


class RepresentedVariable(models.Model):
    type = models.CharField(max_length=255, choices=(('question', 'question'), ('var_internal', 'variable interne'), ('var_recalc', 'variable calcule')))  # question = variable direct
    # origin = models.ManyToManyField('self', symmetrical=False, related_name="children_variables")  # plutot faire une autre class ?

    # hidden = models.BooleanField(default=True)  # probablement a changer pour avoir plus de niveau

    conceptual_var = models.ForeignKey(ConceptualVariable, on_delete=models.CASCADE)
    question_text = models.TextField(null=True)  # uniquement pour les questions, sinon a none
    internal_label = models.CharField(null=True, max_length=255)  # init a variable_label le plus recent?

    categories = models.ManyToManyField(Category, related_name="variables")  # plutot faire une autre class ? (BindingCategory)
    type_categories = models.CharField(max_length=255, choices=(('code', 'code'), ('text', 'text'), ('numerical', 'numerical'), ('date', 'date')))

    def __str__(self):
        return f"Represented Variable: {self.internal_label or 'N/A'} ({self.type}, {self.question_text})"




class BindingSurveyRepresentedVariable(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    variable = models.ForeignKey(RepresentedVariable, on_delete=models.CASCADE)
    notes = models.TextField()
    variable_name = models.TextField()
    universe = models.TextField()

    def __str__(self):
        return f"Binding: {self.variable_name} - Survey: {self.survey.name}"


class Concept(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return f"Concept: {self.name}"


class BindingConcept(models.Model):
    parent = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name="parent_bindings")
    child = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name="child_bindings")

    class Meta:
        unique_together = ('parent', 'child')

    def __str__(self):
        return f"Binding Concept: {self.parent.name} -> {self.child.name}"

