# -- STDLIB
from collections import defaultdict

# -- DJANGO
from django.db import models

# -- REQUEST_DDI (LOCAL)
from request_ddi.utils.normalize_string import normalize_string_for_comparison


class Distributor(models.Model):
    name = models.CharField(max_length=510)

    def __str__(self):
        return self.name


class Collection(models.Model):
    name = models.CharField()
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, null=True, blank=True)
    abstract = models.TextField(default="")

    def __str__(self):
        return f"{self.name}"


class Subcollection(models.Model):
    name = models.CharField()
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.name}"


class Survey(models.Model):
    subcollection = models.ForeignKey(Subcollection, on_delete=models.CASCADE, null=True)
    external_ref = models.CharField(max_length=255, unique=True)
    name = models.TextField()
    date_last_version = models.DateField(null=True, blank=True)
    language = models.CharField(max_length=510, default="")

    # Authors can be a long text dependening on number of authors
    author = models.TextField(null=True, blank=True)
    producer = models.CharField(max_length=510, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    geographic_coverage = models.CharField(max_length=510, null=True, blank=True)
    geographic_unit = models.CharField(max_length=510, null=True, blank=True)
    unit_of_analysis = models.CharField(max_length=510, null=True, blank=True)
    contact = models.EmailField(null=True, blank=True)
    citation = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}"


class ConceptualVariable(models.Model):
    internal_label = models.TextField()
    concepts = models.ManyToManyField(
        "Concept", symmetrical=False, related_name="conceptual_variables"
    )
    is_unique = models.BooleanField(default=False)

    def __str__(self):
        # Récupérer toutes les variables représentées associées
        represented_vars = self.representedvariable_set.all()

        # Si au moins une variable représentée existe, on l'affiche
        if represented_vars.exists():
            return (
                f"Conceptual Variable: {self.internal_label}, Linked Represented Variables: "
                + f"{', '.join([str(var.internal_label) for var in represented_vars])}"
            )
        else:
            return f"Conceptual Variable: {self.internal_label} (No linked represented variables)"


class Category(models.Model):
    """careful when editing a category, most of the time we should be creating a new one instead"""

    code = models.CharField(max_length=255)
    category_label = models.TextField(
        null=True, db_collation="request_ddi_case_accent_insensitive_collation"
    )
    missing = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code} : {self.category_label}"

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["code", "category_label"], name="request_ddi_unique_code_category_link"
            )
        ]


class RepresentedVariable(models.Model):
    type = models.CharField(
        max_length=255,
        choices=(
            ("question", "question"),
            ("var_internal", "variable interne"),
            ("var_recalc", "variable calcule"),
        ),
    )
    # plutot faire une autre class ?
    # origin = models.ManyToManyField('self', symmetrical=False, related_name="children_variables")

    # hidden = models.BooleanField(default=True)  # probablement a changer pour avoir plus de niveau

    conceptual_var = models.ForeignKey(ConceptualVariable, on_delete=models.CASCADE)
    question_text = models.TextField(
        null=True, db_collation="request_ddi_case_accent_insensitive_collation"
    )  # uniquement pour les questions, sinon a none
    internal_label = models.CharField(
        null=True, max_length=510, db_collation="request_ddi_case_accent_insensitive_collation"
    )  # init a variable_label le plus recent?

    categories = models.ManyToManyField(
        Category, related_name="variables"
    )  # plutot faire une autre class ? (BindingCategory)
    type_categories = models.CharField(
        max_length=255,
        choices=(
            ("code", "code"),
            ("text", "text"),
            ("numerical", "numerical"),
            ("date", "date"),
        ),
    )
    is_unique = models.BooleanField(default=False)

    def __str__(self):
        return (
            f"Represented Variable: {self.internal_label or 'N/A'} "
            + f"({self.type}, {self.question_text})"
        )

    @classmethod
    def get_cleaned_question_texts(cls):
        """
        Retourne un dictionnaire : texte nettoyé → liste des variables ayant ce texte.
        Utile pour identifier toutes les variables représentées ayant la même question.
        """
        cleaned = defaultdict(list)
        for var in cls.objects.all():
            key = normalize_string_for_comparison(var.question_text)
            cleaned[key].append(var)
        return dict(cleaned)


class BindingSurveyRepresentedVariable(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    variable = models.ForeignKey(RepresentedVariable, on_delete=models.CASCADE)
    notes = models.TextField()
    variable_name = models.TextField()
    universe = models.TextField()
    is_indexed = models.BooleanField(default=False)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["survey", "variable_name"],
                name="request_ddi_unique_variable_name_per_survey",
            )
        ]

    def __str__(self):
        return f"Binding: {self.variable_name} - Survey: {self.survey.name}"


class Concept(models.Model):
    name = models.CharField(max_length=510)
    description = models.TextField()

    def __str__(self):
        return f"Concept: {self.name}"


class BindingConcept(models.Model):
    parent = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name="parent_bindings")
    child = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name="child_bindings")

    class Meta:
        unique_together = ("parent", "child")

    def __str__(self):
        return f"Binding Concept: {self.parent.name} -> {self.child.name}"


class BindingVariableCategoryStat(models.Model):
    binding = models.ForeignKey(BindingSurveyRepresentedVariable, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    stat = models.IntegerField(default=0)

    class Meta:
        unique_together = ("binding", "category")

    def __str__(self):
        return f"{self.binding.variable_name} - {self.category.code}: {self.stat}"


class UploadedDDIXMLFile(models.Model):
    """Fichier DDI-C XML déposé directement par un utilisateur, sans passer par une URL.

    Une ligne CSV d'import dont la colonne `url` est vide est résolue en cherchant
    ici le fichier dont le DOI correspond, plutôt qu'en le téléchargeant. La ligne est
    supprimée dès que l'import qui l'a consommée réussit : un force_import ultérieur sur
    ce DOI échoue alors exactement comme si le fichier n'avait jamais été déposé, et
    exige donc un nouveau dépôt.
    """

    doi = models.CharField(max_length=255, unique=True)
    original_filename = models.CharField(max_length=255)
    # TextField (Postgres `text`, jusqu'à 1 Go) plutôt qu'un fichier sur disque : évite
    # d'avoir à échapper le "/" du DOI en nom de fichier, et pas d'infra de volume à
    # maintenir. Vérifié contre l'ingress de prod (`proxy-body-size: 100m`, timeouts à
    # 3600s) : suffisant même pour les futurs DDI-Lifecycle, plus volumineux que le DDI-C.
    xml_content = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.doi
