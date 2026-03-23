import os
from datetime import time

import xlrd
from django.core.management.base import BaseCommand

from applications.health_center.models import Doctor, Doctors_Schedule


class Command(BaseCommand):
    help = "Import doctor schedule from Doctor-Schedule.xlsx"

    def handle(self, *args, **options):
        excel_path = os.path.join(os.getcwd(), "dbinsertscripts/healthcenter/Doctor-Schedule.xlsx")
        excel = xlrd.open_workbook(excel_path)
        sheet = excel.sheet_by_index(0)

        day_map = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6,
        }

        imported = 0
        for row in range(1, sheet.nrows):
            doctor_name = str(sheet.cell(row, 0).value)
            day_name = str(sheet.cell(row, 1).value)
            from_raw = int(sheet.cell(row, 2).value * 24 * 3600)
            to_raw = int(sheet.cell(row, 3).value * 24 * 3600)
            room = int(sheet.cell(row, 4).value)

            doctor = Doctor.objects.filter(doctor_name=doctor_name).first()
            if doctor is None or day_name not in day_map:
                continue

            Doctors_Schedule.objects.update_or_create(
                doctor_id=doctor,
                day=day_map[day_name],
                defaults={
                    "from_time": time(from_raw // 3600, (from_raw % 3600) // 60, from_raw % 60),
                    "to_time": time(to_raw // 3600, (to_raw % 3600) // 60, to_raw % 60),
                    "room": room,
                },
            )
            imported += 1

        self.stdout.write(self.style.SUCCESS(f"Imported/updated {imported} schedule rows"))
