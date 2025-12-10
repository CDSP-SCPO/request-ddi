import unittest

from django.db import IntegrityError
from django.test import TestCase

from request_ddi.core.models import (
    BindingConcept,
    BindingSurveyRepresentedVariable,
    Category,
    Collection,
    Concept,
    ConceptualVariable,
    Distributor,
    RepresentedVariable,
    Subcollection,
    Survey,
)

from . import is_elasticsearch_available


class ModelStrTests(TestCase):
    """Tests des méthodes __str__ des différents modèles."""

    @classmethod
    def setUpTestData(cls):
        cls.distributor = Distributor.objects.create(name="Insee")
        cls.collection = Collection.objects.create(name="CDSP", distributor=cls.distributor)
        cls.subcollection = Subcollection.objects.create(name="ESS", collection=cls.collection)
        cls.survey = Survey.objects.create(name="Enquête Santé", external_ref="doi:12345")
        cls.category = Category.objects.create(code="1", category_label="Homme")
        cls.concept_parent = Concept.objects.create(name="Parent", description="desc")
        cls.concept_child = Concept.objects.create(name="Child", description="desc")
        cls.binding_concept = BindingConcept.objects.create(
            parent=cls.concept_parent, child=cls.concept_child
        )

    def test_distributor_str(self):
        self.assertEqual(str(self.distributor), "Insee")

    def test_collection_str(self):
        self.assertEqual(str(self.collection), "CDSP")

    def test_subcollection_str(self):
        self.assertEqual(str(self.subcollection), "ESS")

    def test_survey_str(self):
        self.assertEqual(str(self.survey), "Enquête Santé")

    def test_category_str(self):
        self.assertEqual(str(self.category), "1 : Homme")

    def test_concept_str(self):
        self.assertEqual(str(self.concept_parent), "Concept: Parent")

    def test_binding_concept_str(self):
        self.assertEqual(str(self.binding_concept), "Binding Concept: Parent -> Child")


class RepresentedVariableTests(TestCase):
    """Tests de la logique des RepresentedVariable, notamment le regroupement de questions similaires."""

    def test_get_cleaned_question_texts_groups_similar_questions(self):
        conceptual = ConceptualVariable.objects.create(internal_label="TestVar")

        RepresentedVariable.objects.create(
            conceptual_var=conceptual,
            type="question",
            question_text="Combien possédez-vous d'enfants ?",
            internal_label="Q1",
            type_categories="text",
        )

        RepresentedVariable.objects.create(
            conceptual_var=conceptual,
            type="question",
            question_text="Combien possedez-vous d'enfants ?",  # même question sans accent
            internal_label="Q2",
            type_categories="text",
        )

        grouped = RepresentedVariable.get_cleaned_question_texts()
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(next(iter(grouped.values()))), 2)


class ModelConstraintTests(TestCase):
    def test_category_unique_constraint(self):
        Category.objects.create(code="1", category_label="Homme")
        with self.assertRaises(IntegrityError):
            Category.objects.create(code="1", category_label="Homme")

    def test_binding_concept_unique_together(self):
        parent = Concept.objects.create(name="Parent", description="desc")
        child = Concept.objects.create(name="Child", description="desc")
        BindingConcept.objects.create(parent=parent, child=child)
        with self.assertRaises(IntegrityError):
            BindingConcept.objects.create(parent=parent, child=child)

    @unittest.skipIf(not is_elasticsearch_available(), "elastic search is required for this test")
    def test_binding_survey_variable_unique_constraint(self):
        survey = Survey.objects.create(name="ESS", external_ref="doi:12345")
        conceptual = ConceptualVariable.objects.create(internal_label="var")
        var = RepresentedVariable.objects.create(
            conceptual_var=conceptual,
            type="question",
            question_text="Texte",
            internal_label="Q1",
            type_categories="text",
        )
        BindingSurveyRepresentedVariable.objects.create(
            survey=survey,
            variable=var,
            notes="note",
            variable_name="Q1",
            universe="Tous",
        )
        with self.assertRaises(IntegrityError):
            BindingSurveyRepresentedVariable.objects.create(
                survey=survey,
                variable=var,
                notes="note2",
                variable_name="Q1",
                universe="Tous",
            )
