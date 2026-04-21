import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from applications.globals.models import DepartmentInfo, Designation, ExtraInfo, HoldsDesignation
from applications.health_center.models import All_Medicine, Doctor, Present_Stock, Stock_entry


class Command(BaseCommand):
    help = "Seed mock health center data (doctors, compounders, medicines, stock)."

    def add_arguments(self, parser):
        parser.add_argument("--doctors", type=int, default=40)
        parser.add_argument("--compounders", type=int, default=20)
        parser.add_argument("--medicines", type=int, default=150)
        parser.add_argument("--stock-per-medicine", type=int, default=3)
        parser.add_argument("--seed", type=int, default=20260420)

    def handle(self, *args, **options):
        random.seed(options["seed"])

        doctors_target = max(0, options["doctors"])
        compounders_target = max(0, options["compounders"])
        medicines_target = max(0, options["medicines"])
        stock_per_medicine = max(0, options["stock_per_medicine"])

        created_doctors = 0
        updated_doctors = 0
        created_compounders = 0
        updated_compounders = 0
        created_medicines = 0
        updated_medicines = 0
        created_stock_entries = 0

        department, _ = DepartmentInfo.objects.get_or_create(name="Health Center")
        designation, _ = Designation.objects.get_or_create(
            name="compounder",
            defaults={"full_name": "Compounder", "type": "administrative"},
        )

        specializations = [
            "General Physician",
            "ENT",
            "Orthopedics",
            "Dermatology",
            "Cardiology",
            "Neurology",
            "Gastroenterology",
            "Pulmonology",
            "Pediatrics",
            "Psychiatry",
        ]

        for idx in range(1, doctors_target + 1):
            doctor_name = f"Dr. Mock Doctor {idx:03d}"
            phone = f"9{idx:09d}"[-10:]
            specialization = specializations[(idx - 1) % len(specializations)]

            _, created = Doctor.objects.update_or_create(
                doctor_name=doctor_name,
                defaults={
                    "doctor_phone": phone,
                    "specialization": specialization,
                    "active": True,
                },
            )
            if created:
                created_doctors += 1
            else:
                updated_doctors += 1

        for idx in range(1, compounders_target + 1):
            username = f"mockcmp{idx:03d}"
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": "Mock",
                    "last_name": f"Compounder{idx:03d}",
                    "email": f"{username}@fusion.local",
                },
            )
            if user_created:
                user.set_password("mock12345")
                user.save(update_fields=["password"])

            extra_id = f"CMPD{idx:04d}"
            extra_defaults = {
                "user": user,
                "title": "Mr.",
                "sex": "M",
                "user_status": "PRESENT",
                "address": "Health Center Block",
                "phone_no": int(f"8{idx:09d}"[-10:]),
                "user_type": "compounder",
                "department": department,
                "about_me": "Mock compounder for development/testing",
            }
            extra, extra_created = ExtraInfo.objects.get_or_create(id=extra_id, defaults=extra_defaults)

            fields_to_update = []
            if extra.user_id != user.id:
                extra.user = user
                fields_to_update.append("user")
            if extra.user_type != "compounder":
                extra.user_type = "compounder"
                fields_to_update.append("user_type")
            if extra.department_id != department.id:
                extra.department = department
                fields_to_update.append("department")
            if fields_to_update:
                extra.save(update_fields=fields_to_update)

            HoldsDesignation.objects.get_or_create(
                user=user,
                working=user,
                designation=designation,
            )

            if extra_created:
                created_compounders += 1
            else:
                updated_compounders += 1

        constituents_pool = [
            "Paracetamol 500mg",
            "Amoxicillin 250mg",
            "Cetirizine 10mg",
            "Ibuprofen 400mg",
            "Azithromycin 500mg",
            "Metformin 500mg",
            "Pantoprazole 40mg",
            "ORS + Electrolytes",
            "Vitamin C 500mg",
            "Calcium + D3",
        ]

        for idx in range(1, medicines_target + 1):
            brand_name = f"MockBrand-{idx:03d}"
            medicine_name = f"MockMedicine-{idx:03d}"
            constituents = constituents_pool[(idx - 1) % len(constituents_pool)]
            manufacturer_name = f"Mock Pharma {(idx % 25) + 1:02d}"
            threshold = random.randint(20, 120)
            pack_size_label = random.choice(["10 tablets", "15 tablets", "1 bottle", "20 capsules"])

            _, created = All_Medicine.objects.update_or_create(
                brand_name=brand_name,
                defaults={
                    "medicine_name": medicine_name,
                    "constituents": constituents,
                    "manufacturer_name": manufacturer_name,
                    "threshold": threshold,
                    "pack_size_label": pack_size_label,
                },
            )
            if created:
                created_medicines += 1
            else:
                updated_medicines += 1

        seeded_medicines = list(
            All_Medicine.objects.filter(brand_name__startswith="MockBrand-").order_by("brand_name")[:medicines_target]
        )
        today = timezone.now().date()

        for med_index, medicine in enumerate(seeded_medicines, start=1):
            for batch in range(1, stock_per_medicine + 1):
                quantity = random.randint(80, 600)
                supplier = f"Mock Supplier {((med_index + batch) % 18) + 1:02d}"
                expiry = today + timedelta(days=random.randint(45, 1100))

                existing = Stock_entry.objects.filter(
                    medicine_id=medicine,
                    quantity=quantity,
                    supplier=supplier,
                    Expiry_date=expiry,
                ).first()
                if existing:
                    Present_Stock.objects.get_or_create(
                        stock_id=existing,
                        defaults={
                            "medicine_id": medicine,
                            "quantity": quantity,
                            "Expiry_date": expiry,
                        },
                    )
                    continue

                stock_entry = Stock_entry.objects.create(
                    medicine_id=medicine,
                    quantity=quantity,
                    supplier=supplier,
                    Expiry_date=expiry,
                )
                Present_Stock.objects.create(
                    medicine_id=medicine,
                    stock_id=stock_entry,
                    quantity=quantity,
                    Expiry_date=expiry,
                )
                created_stock_entries += 1

        self.stdout.write(self.style.SUCCESS("Mock health center data seeded successfully."))
        self.stdout.write(
            self.style.SUCCESS(
                "Doctors: +{created} created, {updated} updated | "
                "Compounders: +{c_created} created, {c_updated} updated | "
                "Medicines: +{m_created} created, {m_updated} updated | "
                "Stock entries: +{s_created} created".format(
                    created=created_doctors,
                    updated=updated_doctors,
                    c_created=created_compounders,
                    c_updated=updated_compounders,
                    m_created=created_medicines,
                    m_updated=updated_medicines,
                    s_created=created_stock_entries,
                )
            )
        )
