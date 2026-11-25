from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("request_ddi", "0020_uploadedddixmlfile"),
    ]

    operations = [
        migrations.RenameField(
            model_name="uploadedddixmlfile",
            old_name="doi",
            new_name="ddi_id",
        ),
    ]
