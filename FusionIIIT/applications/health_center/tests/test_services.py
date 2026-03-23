from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from applications.health_center.api.services import prescribe_medicine
from applications.health_center.models import (
    All_Medicine,
    All_Prescription,
    Present_Stock,
    Stock_entry,
)


class PrescribeMedicineServiceTests(TestCase):
    def setUp(self):
        self.medicine = All_Medicine.objects.create(
            medicine_name="Paracetamol",
            brand_name="PCM-500",
            constituents="Paracetamol",
            manufacturer_name="Acme",
            threshold=5,
            pack_size_label="10 tablets",
        )
        self.prescription = All_Prescription.objects.create(
            user_id="student001",
            doctor_id=None,
            details="Fever",
            date=timezone.now().date(),
            suggestions="Rest",
            test="",
            file_id=0,
        )

    def test_prescribe_sufficient_stock(self):
        future_date = timezone.now().date() + timedelta(days=10)
        stock_entry = Stock_entry.objects.create(
            medicine_id=self.medicine,
            quantity=20,
            supplier="MedSupplier",
            Expiry_date=future_date,
        )
        Present_Stock.objects.create(
            quantity=20,
            stock_id=stock_entry,
            medicine_id=self.medicine,
            Expiry_date=future_date,
        )

        result = prescribe_medicine(self.medicine.id, 5, self.prescription.id)

        self.assertTrue(result["success"])
        self.assertEqual(result["remaining_stock"], 15)

    def test_prescribe_insufficient_stock(self):
        future_date = timezone.now().date() + timedelta(days=10)
        stock_entry = Stock_entry.objects.create(
            medicine_id=self.medicine,
            quantity=2,
            supplier="MedSupplier",
            Expiry_date=future_date,
        )
        Present_Stock.objects.create(
            quantity=2,
            stock_id=stock_entry,
            medicine_id=self.medicine,
            Expiry_date=future_date,
        )

        result = prescribe_medicine(self.medicine.id, 5, self.prescription.id)

        self.assertFalse(result["success"])
        self.assertEqual(result["remaining_stock"], 2)

    def test_prescribe_expired_only(self):
        expired_date = timezone.now().date() - timedelta(days=1)
        stock_entry = Stock_entry.objects.create(
            medicine_id=self.medicine,
            quantity=10,
            supplier="MedSupplier",
            Expiry_date=expired_date,
        )
        Present_Stock.objects.create(
            quantity=10,
            stock_id=stock_entry,
            medicine_id=self.medicine,
            Expiry_date=expired_date,
        )

        result = prescribe_medicine(self.medicine.id, 1, self.prescription.id)

        self.assertFalse(result["success"])
        self.assertEqual(result["remaining_stock"], 0)
