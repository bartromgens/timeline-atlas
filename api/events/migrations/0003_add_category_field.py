from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_add_importance_score_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="category",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
