from django.db import migrations, models
import django.db.models.deletion
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ("health_center", "0015_healthcenterfeedback"),
    ]

    operations = [
        migrations.CreateModel(
            name="DoctorAttendance",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attendance_date", models.DateField(default=datetime.date.today)),
                ("is_present", models.BooleanField(default=False)),
                ("marked_at", models.DateTimeField(auto_now=True)),
                (
                    "doctor_id",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="health_center.doctor"),
                ),
                (
                    "marked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="marked_doctor_attendance",
                        to="globals.extrainfo",
                    ),
                ),
            ],
            options={
                "unique_together": {("doctor_id", "attendance_date")},
            },
        ),
    ]
