import os

import xlrd
from django.core.management.base import BaseCommand

from applications.health_center.models import Doctor


class Command(BaseCommand):
    help = "Import doctors from Doctor-List.xlsx"

    def handle(self, *args, **options):
        excel_path = os.path.join(os.getcwd(), "dbinsertscripts/healthcenter/Doctor-List.xlsx")
        excel = xlrd.open_workbook(excel_path)
        sheet = excel.sheet_by_index(0)

        imported = 0
        for row in range(1, sheet.nrows):
            name = str(sheet.cell(row, 0).value)
            phone = str(int(sheet.cell(row, 1).value))
            specialization = str(sheet.cell(row, 2).value)
            Doctor.objects.update_or_create(
                doctor_name=name,
                defaults={
                    "doctor_phone": phone,
                    "specialization": specialization,
                    "active": True,
                },
            )
            imported += 1

        self.stdout.write(self.style.SUCCESS(f"Imported/updated {imported} doctors"))
