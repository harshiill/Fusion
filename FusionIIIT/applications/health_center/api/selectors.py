from datetime import datetime

from applications.globals.models import ExtraInfo
from applications.globals.models import HoldsDesignation

from ..models import (
    All_Medicine,
    All_Prescribed_medicine,
    All_Prescription,
    Doctor,
    Doctors_Schedule,
    Pathologist,
    Pathologist_Schedule,
    Present_Stock,
    Required_medicine,
    Stock_entry,
    InventoryRequisition,
)


class ScheduleNotFound(Exception):
    pass


def ping_selector():
    return True


def get_designations_for_user(user):
    designations = []
    user_type = getattr(user.extrainfo, "user_type", None)
    if user_type:
        designations.append(str(user_type))
    for row in HoldsDesignation.objects.select_related("designation").filter(working=user):
        designation = str(row.designation)
        if designation not in designations:
            designations.append(designation)
    return designations


def get_compounder_dashboard_data():
    """
    Returns all data needed for compounder dashboard.
    """
    return {
        "users": ExtraInfo.objects.select_related("user", "department").filter(user_type="student"),
        "doctors": Doctor.objects.filter(active=True).order_by("id"),
        "pathologists": Pathologist.objects.filter(active=True).order_by("id"),
        "doctor_schedule": Doctors_Schedule.objects.select_related("doctor_id").all().order_by("day", "doctor_id"),
        "pathologist_schedule": Pathologist_Schedule.objects.select_related("pathologist_id").all().order_by("day", "pathologist_id"),
        "required_medicines": Required_medicine.objects.select_related("medicine_id").all(),
        "expired_stock": Stock_entry.objects.select_related("medicine_id").filter(Expiry_date__lt=datetime.now().date()).order_by("Expiry_date"),
        "live_stock": Stock_entry.objects.select_related("medicine_id").filter(Expiry_date__gte=datetime.now().date()).order_by("Expiry_date"),
        "prescriptions": All_Prescription.objects.select_related("doctor_id").all().order_by("-date", "-id"),
        "prescribed_medicines": All_Prescribed_medicine.objects.select_related("prescription_id", "medicine_id").all(),
    }


def get_student_dashboard_data(user):
    """
    Returns all data needed for student dashboard.
    """
    user_info = ExtraInfo.objects.select_related("user", "department").get(user=user)
    prescriptions = All_Prescription.objects.select_related("doctor_id").filter(user_id=user.username).order_by("-date", "-id")
    return {
        "user_info": user_info,
        "doctors": Doctor.objects.filter(active=True).order_by("id"),
        "pathologists": Pathologist.objects.filter(active=True).order_by("id"),
        "doctor_schedule": Doctors_Schedule.objects.select_related("doctor_id").all().order_by("doctor_id"),
        "pathologist_schedule": Pathologist_Schedule.objects.select_related("pathologist_id").all().order_by("pathologist_id"),
        "prescriptions": prescriptions,
        "prescribed_medicines": All_Prescribed_medicine.objects.select_related("prescription_id", "medicine_id").filter(
            prescription_id__in=prescriptions
        ),
        "stock": Present_Stock.objects.select_related("medicine_id", "stock_id").filter(Expiry_date__gte=datetime.now().date()),
        "medicines": All_Medicine.objects.all().order_by("brand_name"),
    }


def get_schedule_for_appointment(doctor_id, date_str):
    """
    Parses date_str, finds the matching Schedule, returns it or raises ScheduleNotFound.
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ScheduleNotFound("Invalid date format. Expected YYYY-MM-DD") from exc

    day_value = date_obj.weekday()
    schedule = Doctors_Schedule.objects.select_related("doctor_id").filter(doctor_id=doctor_id, day=day_value).first()
    if schedule is None:
        raise ScheduleNotFound("Schedule not found for selected doctor/day")
    return schedule


def get_all_requisitions():
    return InventoryRequisition.objects.select_related("originator", "approved_by").prefetch_related("items", "items__medicine_id").all().order_by("-created_at")

def get_requisitions_for_staff(user):
    return get_all_requisitions().filter(originator=user)

def get_pending_requisitions():
    return get_all_requisitions().filter(status=InventoryRequisition.STATUS_SUBMITTED)

def get_requisition_by_id(req_id):
    return get_all_requisitions().filter(id=req_id).first()