import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0006_add_wikipedia_extract"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(blank=True, max_length=500)),
                ("wikidata_id", models.CharField(max_length=20, unique=True)),
                ("wikidata_url", models.URLField(blank=True, max_length=500)),
            ],
            options={
                "verbose_name_plural": "event types",
            },
        ),
        migrations.AddField(
            model_name="event",
            name="event_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="events",
                to="events.eventtype",
            ),
        ),
    ]
