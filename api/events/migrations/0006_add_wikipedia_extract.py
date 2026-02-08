from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0005_category_cascade_delete"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="wikipedia_extract",
            field=models.TextField(blank=True, default=""),
        ),
    ]
