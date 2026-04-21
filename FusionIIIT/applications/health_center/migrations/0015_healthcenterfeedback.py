from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("globals", "0001_initial"),
        ("health_center", "0014_alter_medicalprofile_optional_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="HealthCenterFeedback",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("complaint", models.TextField()),
                ("feedback", models.TextField(blank=True, default="")),
                ("date", models.DateTimeField(auto_now_add=True)),
                (
                    "user_id",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="globals.extrainfo"),
                ),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
    ]
