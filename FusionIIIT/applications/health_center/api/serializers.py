from datetime import date

from rest_framework import serializers

from ..models import (
    Announcement,
    All_Medicine,
    All_Prescribed_medicine,
    All_Prescription,
    Doctor,
    DoctorAttendance,
    Doctors_Schedule,
    MedicalRelief,
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
        if len(digits) < 7 or len(digits) > 15:
            raise serializers.ValidationError("Pathologist phone must contain 7-15 digits.")
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

    def validate(self, data):
        from_time = data.get("from_time")
        to_time = data.get("to_time")
        doctor = data.get("doctor_id")
        day = data.get("day")

        if from_time and to_time and from_time >= to_time:
            raise serializers.ValidationError({"from_time": "from_time must be earlier than to_time."})

        overlaps = Doctors_Schedule.objects.filter(
            doctor_id=doctor,
            day=day,
            from_time__lt=to_time,
            to_time__gt=from_time,
        )
        if self.instance:
            overlaps = overlaps.exclude(id=self.instance.id)
        if overlaps.exists():
            raise serializers.ValidationError("Schedule conflict for this doctor and day.")
        return data


class DoctorAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorAttendance
        fields = ["id", "doctor_id", "attendance_date", "is_present", "marked_by", "marked_at"]
        read_only_fields = ["id", "marked_by", "marked_at"]


class PathologistScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pathologist_Schedule
        fields = ["id", "pathologist_id", "day", "from_time", "to_time", "room", "date"]
        read_only_fields = ["id", "date"]

    def validate(self, data):
        from_time = data.get("from_time")
        to_time = data.get("to_time")
        pathologist = data.get("pathologist_id")
        day = data.get("day")

        if from_time and to_time and from_time >= to_time:
            raise serializers.ValidationError({"from_time": "from_time must be earlier than to_time."})

        overlaps = Pathologist_Schedule.objects.filter(
            pathologist_id=pathologist,
            day=day,
            from_time__lt=to_time,
            to_time__gt=from_time,
        )
        if self.instance:
            overlaps = overlaps.exclude(id=self.instance.id)
        if overlaps.exists():
            raise serializers.ValidationError("Schedule conflict for this pathologist and day.")
        return data


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
            "follow_up_of",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        if data.get("is_dependent"):
            dependent_name = (data.get("dependent_name") or "").strip()
            dependent_relation = (data.get("dependent_relation") or "").strip()
            if not dependent_name or dependent_name.upper() == "SELF":
                raise serializers.ValidationError(
                    {"dependent_name": "Required when is_dependent is true."}
                )
            if not dependent_relation or dependent_relation.upper() == "SELF":
                raise serializers.ValidationError(
                    {"dependent_relation": "Required when is_dependent is true."}
                )
        return data


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


class MedicalReliefWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRelief
        fields = ["id", "user_id", "description", "file", "status", "reviewed_by", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "reviewed_by", "created_at", "updated_at"]


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "message", "ann_date", "file", "created_by"]
        read_only_fields = ["id", "ann_date", "created_by"]

    def validate_message(self, value):
        message = (value or "").strip()
        if not message:
            raise serializers.ValidationError("Announcement message cannot be empty.")
        if len(message) > 200:
            raise serializers.ValidationError("Message cannot exceed 200 characters.")
        return message


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
            "blood_group",
            "allergies",
            "chronic_conditions",
            "emergency_contact",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "date_of_birth": {"required": False, "allow_null": True},
            "gender": {"required": False, "allow_null": True, "allow_blank": True},
            "blood_type": {"required": False, "allow_null": True, "allow_blank": True},
            "height": {"required": False, "allow_null": True},
            "weight": {"required": False, "allow_null": True},
            "blood_group": {"required": False, "allow_null": True, "allow_blank": True},
            "allergies": {"required": False, "allow_null": True, "allow_blank": True},
            "chronic_conditions": {"required": False, "allow_null": True, "allow_blank": True},
            "emergency_contact": {"required": False, "allow_null": True, "allow_blank": True},
        }


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
