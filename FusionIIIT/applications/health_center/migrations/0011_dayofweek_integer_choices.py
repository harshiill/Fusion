from django.db import migrations, models


def convert_day_values(apps, schema_editor):
    doctor_schedule = apps.get_model("health_center", "Doctors_Schedule")
    pathologist_schedule = apps.get_model("health_center", "Pathologist_Schedule")
    day_map = {
        "0": 0,
        "1": 1,
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "6": 6,
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

    for model in (doctor_schedule, pathologist_schedule):
        for row in model.objects.all().only("id", "day"):
            normalized_value = day_map.get(str(row.day), 0)
            model.objects.filter(pk=row.pk).update(day=normalized_value)


class Migration(migrations.Migration):

    dependencies = [
        ("health_center", "0010_auto_20240727_2352"),
    ]

    operations = [
        migrations.RunPython(convert_day_values, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="doctors_schedule",
            name="day",
            field=models.IntegerField(
                choices=[
                    (0, "Monday"),
                    (1, "Tuesday"),
                    (2, "Wednesday"),
                    (3, "Thursday"),
                    (4, "Friday"),
                    (5, "Saturday"),
                    (6, "Sunday"),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="pathologist_schedule",
            name="day",
            field=models.IntegerField(
                choices=[
                    (0, "Monday"),
                    (1, "Tuesday"),
                    (2, "Wednesday"),
                    (3, "Thursday"),
                    (4, "Friday"),
                    (5, "Saturday"),
                    (6, "Sunday"),
                ]
            ),
        ),
    ]
