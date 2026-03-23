from datetime import date

from rest_framework import serializers

from ..models import (
    All_Medicine,
    All_Prescribed_medicine,
    All_Prescription,
    Doctor,
    Doctors_Schedule,
    MedicalProfile,
    Pathologist,
    Pathologist_Schedule,
    Present_Stock,
    Required_medicine,
    Stock_entry,
    medical_relief,
)


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ["id", "doctor_name", "doctor_phone", "specialization", "active"]
        read_only_fields = ["id"]

    def validate_doctor_phone(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 10:
            raise serializers.ValidationError("Doctor phone must contain exactly 10 digits.")
        return value


class PathologistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pathologist
        fields = ["id", "pathologist_name", "pathologist_phone", "specialization", "active"]
        read_only_fields = ["id"]

    def validate_pathologist_phone(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 10:
            raise serializers.ValidationError("Pathologist phone must contain exactly 10 digits.")
        return value


class AllMedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = All_Medicine
        fields = [
            "id",
            "medicine_name",
            "brand_name",
            "constituents",
            "manufacturer_name",
            "threshold",
            "pack_size_label",
        ]
        read_only_fields = ["id"]

    def validate_threshold(self, value):
        if value < 0:
            raise serializers.ValidationError("Threshold cannot be negative.")
        return value


class StockEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock_entry
        fields = ["id", "medicine_id", "quantity", "supplier", "Expiry_date", "date"]
        read_only_fields = ["id", "date"]

    def validate_Expiry_date(self, value):
        if value < date.today():
            raise serializers.ValidationError("Expiry date must be today or in the future.")
        return value


class PresentStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Present_Stock
        fields = ["id", "quantity", "stock_id", "medicine_id", "Expiry_date"]
        read_only_fields = ["id"]


class RequiredMedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Required_medicine
        fields = ["id", "medicine_id", "quantity", "threshold"]
        read_only_fields = ["id"]


class DoctorsScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctors_Schedule
        fields = ["id", "doctor_id", "day", "from_time", "to_time", "room", "date"]
        read_only_fields = ["id", "date"]


class PathologistScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pathologist_Schedule
        fields = ["id", "pathologist_id", "day", "from_time", "to_time", "room", "date"]
        read_only_fields = ["id", "date"]


class AllPrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = All_Prescription
        fields = [
            "id",
            "user_id",
            "doctor_id",
            "details",
            "date",
            "suggestions",
            "test",
            "file_id",
            "is_dependent",
            "dependent_name",
            "dependent_relation",
        ]
        read_only_fields = ["id"]


class AllPrescribedMedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = All_Prescribed_medicine
        fields = [
            "id",
            "prescription_id",
            "medicine_id",
            "stock",
            "prescription_followup_id",
            "quantity",
            "days",
            "times",
            "revoked",
            "revoked_date",
            "revoked_prescription",
        ]
        read_only_fields = ["id"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class MedicalReliefSerializer(serializers.ModelSerializer):
    class Meta:
        model = medical_relief
        fields = [
            "id",
            "description",
            "file",
            "file_id",
            "compounder_forward_flag",
            "acc_admin_forward_flag",
        ]
        read_only_fields = ["id", "file_id", "compounder_forward_flag", "acc_admin_forward_flag"]


class MedicalProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalProfile
        fields = [
            "id",
            "user_id",
            "date_of_birth",
            "gender",
            "blood_type",
            "height",
            "weight",
        ]
        read_only_fields = ["id"]


class AmbulanceRequestCreateSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=500)


class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField()
    date = serializers.DateField()
    description = serializers.CharField(max_length=1000)


class ComplaintCreateSerializer(serializers.Serializer):
    complaint = serializers.CharField(max_length=1000)


class ComplaintResponseSerializer(serializers.Serializer):
    complaint_id = serializers.IntegerField()
    feedback = serializers.CharField(max_length=1000)
