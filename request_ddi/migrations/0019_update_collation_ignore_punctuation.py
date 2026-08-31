# Generated manually (not via makemigrations) on 2026-08-24

from django.conf import settings
from django.contrib.postgres.operations import CreateCollation, RemoveCollation
from django.db import migrations

OLD_COLLATION_NAME = settings.DB_COLLATION
TMP_COLLATION_NAME = f"{settings.DB_COLLATION}_tmp"

REPOINT_SQL = [
    f'ALTER TABLE request_ddi_category '
    f'ALTER COLUMN category_label TYPE text COLLATE "{TMP_COLLATION_NAME}"',
    f'ALTER TABLE request_ddi_representedvariable '
    f'ALTER COLUMN question_text TYPE text COLLATE "{TMP_COLLATION_NAME}"',
    f'ALTER TABLE request_ddi_representedvariable '
    f'ALTER COLUMN internal_label TYPE varchar(510) COLLATE "{TMP_COLLATION_NAME}"',
]

REPOINT_REVERSE_SQL = [
    f'ALTER TABLE request_ddi_category '
    f'ALTER COLUMN category_label TYPE text COLLATE "{OLD_COLLATION_NAME}"',
    f'ALTER TABLE request_ddi_representedvariable '
    f'ALTER COLUMN question_text TYPE text COLLATE "{OLD_COLLATION_NAME}"',
    f'ALTER TABLE request_ddi_representedvariable '
    f'ALTER COLUMN internal_label TYPE varchar(510) COLLATE "{OLD_COLLATION_NAME}"',
]

RENAME_SQL = f'ALTER COLLATION "{TMP_COLLATION_NAME}" RENAME TO "{OLD_COLLATION_NAME}"'
RENAME_REVERSE_SQL = f'ALTER COLLATION "{OLD_COLLATION_NAME}" RENAME TO "{TMP_COLLATION_NAME}"'


def repoint_columns(apps, schema_editor):
    # SQLite (used to run the test suite) has no ICU collation support and does not
    # understand this SQL at all. CreateCollation/RemoveCollation already skip
    # themselves on non-postgres backends, so do the same here.
    if schema_editor.connection.vendor != "postgresql":
        return
    for sql in REPOINT_SQL:
        schema_editor.execute(sql)


def repoint_columns_reverse(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for sql in REPOINT_REVERSE_SQL:
        schema_editor.execute(sql)


def rename_collation(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RENAME_SQL)


def rename_collation_reverse(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RENAME_REVERSE_SQL)


class Migration(migrations.Migration):
    """
    Migration 0016 originally created a case/accent-insensitive ICU collation using
    locale="und-u-ks-level1". This migration updates it to ALSO ignore punctuation
    (locale="und-u-ks-level1@colAlternate=shifted"), which improves matching between
    represented variables and binding variables whose question text/labels only
    differ by punctuation.

    PostgreSQL collations cannot be altered in place, and the existing collation
    cannot simply be dropped and recreated because three columns already depend on it
    (Category.category_label, RepresentedVariable.question_text,
    RepresentedVariable.internal_label, see migration 0017). So this migration:

      1. Creates the new collation under a temporary name.
      2. Repoints the three dependent columns to the new collation.
      3. Drops the old collation (safe now that nothing references it).
      4. Renames the new collation back to the original name, so that
         settings.DB_COLLATION and every existing db_collation=... field
         definition keep working unchanged.

    Steps 2 and 4 use RunPython (not RunSQL) so they can skip themselves on
    non-postgres backends, same as CreateCollation/RemoveCollation already do -
    this project's test suite runs on SQLite, which has no ICU collation support.

    In addition to accents and cases, we need to ignore punctuation marks as well when
    comparing texts. This is done using option colAlternate=shifted.
    
    Ref: 
    https://postgresql.verite.pro/blog/2019/10/14/nondeterministic-collations.html
    https://unicode-org.github.io/icu/userguide/collation/customization/ignorepunct.html
    """

    dependencies = [
        ("request_ddi", "0018_alter_survey_author"),
    ]

    operations = [
        # 1. Create the new collation under a temporary name
        CreateCollation(
            TMP_COLLATION_NAME,
            provider="icu",
            locale="und-u-ks-level1@colAlternate=shifted",
            deterministic=False,
        ),
        # 2. Repoint the columns that currently use the old collation
        migrations.RunPython(repoint_columns, repoint_columns_reverse),
        # 3. Drop the old collation (nothing depends on it anymore)
        RemoveCollation(
            OLD_COLLATION_NAME,
            provider="icu",
            locale="und-u-ks-level1",
            deterministic=False,
        ),
        # 4. Rename the new collation back to the original name so that
        #    settings.DB_COLLATION and existing field definitions stay valid
        migrations.RunPython(rename_collation, rename_collation_reverse),
    ]
