from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("runs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="run",
            name="completion_reason",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="run",
            name="ended_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="run",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="run",
            name="missing_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
