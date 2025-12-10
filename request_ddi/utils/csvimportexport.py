# resources.py
# -- THIRDPARTY
# -- BASEDEQUESTIONS (LOCAL)
from app.models import BindingSurveyRepresentedVariable
from import_export import resources
from import_export.fields import Field


class BindingSurveyResource(resources.ModelResource):
    variable_label = Field(attribute="variable__internal_label")
    question_text = Field(attribute="variable__question_text")
    category_label = Field(attribute="variable__categories__category_label")
    var_repr = Field(attribute="variable__internal_label")
    var_conc = Field(attribute="variable__conceptual_var__internal_label")  # Variable conceptuelle

    class Meta:
        model = BindingSurveyRepresentedVariable
        fields = (
            "survey__external_ref",
            "survey__name",
            "variable_name",
            "variable_label",
            "question_text",
            "category_label",
            "universe",
            "notes",
            "var_repr",
            "var_conc",
        )
        export_order = (
            "survey__external_ref",
            "survey__name",
            "variable_name",
            "variable_label",
            "question_text",
            "category_label",
            "universe",
            "notes",
            "var_repr",
            "var_conc",
        )

    def dehydrate_represented_variable_id(self, instance):
        """Retourne l'ID de la variable représentée"""
        return instance.variable.id if instance.variable else None
