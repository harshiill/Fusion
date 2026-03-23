import os

import xlrd
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from applications.globals.models import DepartmentInfo, Designation, ExtraInfo, HoldsDesignation


class Command(BaseCommand):
    help = "Import compounders from Compounder-List.xlsx"

    def handle(self, *args, **options):
        excel_path = os.path.join(os.getcwd(), "dbinsertscripts/healthcenter/Compounder-List.xlsx")
        excel = xlrd.open_workbook(excel_path)
        sheet = excel.sheet_by_index(0)

        imported = 0
        for row in range(1, sheet.nrows):
            empid = int(sheet.cell(row, 0).value)
            full_name = str(sheet.cell(row, 1).value).split()
            department = str(sheet.cell(row, 2).value)
            email = str(sheet.cell(row, 3).value)
            designation_name = str(sheet.cell(row, 4).value)

            username = email.split("@")[0]
            first_name = " ".join(full_name[:-1]) if len(full_name) > 1 else full_name[0]
            last_name = full_name[-1] if len(full_name) > 1 else ""

            dept_obj, _ = DepartmentInfo.objects.get_or_create(name=department)
            designation_obj, _ = Designation.objects.get_or_create(name=designation_name)

            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                },
            )
            if not user.has_usable_password():
                user.set_password("hello123")
                user.save(update_fields=["password"])

            extra, _ = ExtraInfo.objects.get_or_create(
                id=empid,
                defaults={
                    "sex": "M",
                    "user": user,
                    "department": dept_obj,
                    "age": 38,
                    "about_me": f"Hello I am {first_name} {last_name}",
                    "user_type": "compounder",
                    "phone_no": 9999999999,
                },
            )
            if extra.user_id != user.id:
                extra.user = user
                extra.department = dept_obj
                extra.user_type = "compounder"
                extra.save(update_fields=["user", "department", "user_type"])

            HoldsDesignation.objects.get_or_create(
                user=user,
                working=user,
                designation=designation_obj,
            )
            imported += 1

        self.stdout.write(self.style.SUCCESS(f"Imported/updated {imported} compounders"))
