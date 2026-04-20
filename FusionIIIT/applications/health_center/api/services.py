from datetime import datetime

from django.apps import apps
from django.db import transaction

from applications.globals.models import ExtraInfo
from notification.views import healthcare_center_notif

from .selectors import ScheduleNotFound, get_schedule_for_appointment
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
    HealthCenterFeedback,
    medical_relief,
)


def ping_service():
    return True


def _model_or_none(model_name):
    model = globals().get(model_name)
    if model is not None:
        return model

    try:
        return apps.get_model("health_center", model_name)
    except Exception:
        return None


def reset_counter():
    counter_model = _model_or_none("Counter")
    if counter_model is None:
        return None
    counter_model.objects.all().delete()
    return counter_model.objects.create(count=0, fine=0)


@transaction.atomic
def prescribe_medicine(medicine_id, quantity, prescription_id):
    """
    Handles medicine allocation using expiry-based FIFO logic.
    Returns: {success: bool, message: str, remaining_stock: int, prescribed_medicine: All_Prescribed_medicine | None}
    """
    existing_revoked = All_Prescribed_medicine.objects.filter(
        prescription_id_id=prescription_id,
        medicine_id_id=medicine_id,
        revoked=True,
    ).first()
    if existing_revoked:
        return {
            "success": False,
            "message": "This medicine has been revoked and cannot be dispensed.",
            "remaining_stock": 0,
            "error": "This medicine has been revoked and cannot be dispensed.",
        }

    medicine = All_Medicine.objects.get(pk=medicine_id)
    prescription = All_Prescription.objects.get(pk=prescription_id)
    stocks = list(
        Present_Stock.objects.select_related("medicine_id", "stock_id")
        .filter(medicine_id=medicine, quantity__gt=0, Expiry_date__gte=datetime.now().date())
        .order_by("Expiry_date", "id")
    )
    total_stock = sum(stock.quantity for stock in stocks)

    if total_stock < int(quantity):
        return {
            "success": False,
            "message": "Required medicine is not available",
            "remaining_stock": total_stock,
            "error": f"Insufficient stock. Available: {total_stock}, Requested: {int(quantity)}",
        }

    requested_qty = int(quantity)
    first_stock = None
    for stock in stocks:
        if requested_qty <= 0:
            break
        if first_stock is None:
            first_stock = stock
        consumed = min(stock.quantity, requested_qty)
        stock.quantity -= consumed
        stock.save(update_fields=["quantity"])
        requested_qty -= consumed

    prescribed_medicine = All_Prescribed_medicine.objects.create(
        prescription_id=prescription,
        medicine_id=medicine,
        stock=first_stock,
        quantity=int(quantity),
    )

    remaining_stock = (
        Present_Stock.objects.filter(medicine_id=medicine, Expiry_date__gte=datetime.now().date()).aggregate_qty()
        if hasattr(Present_Stock.objects, "aggregate_qty")
        else sum(
            Present_Stock.objects.filter(medicine_id=medicine, Expiry_date__gte=datetime.now().date()).values_list(
                "quantity", flat=True
            )
        )
    )

    if remaining_stock < medicine.threshold:
        req, _ = Required_medicine.objects.get_or_create(
            medicine_id=medicine,
            defaults={"quantity": remaining_stock, "threshold": medicine.threshold},
        )
        req.quantity = remaining_stock
        req.threshold = medicine.threshold
        req.save(update_fields=["quantity", "threshold"])
    else:
        Required_medicine.objects.filter(medicine_id=medicine).delete()

    return {
        "success": True,
        "message": "Medicine prescribed successfully",
        "dispensed": int(quantity),
        "remaining_stock": remaining_stock,
        "prescribed_medicine": prescribed_medicine,
        "error": None,
    }


def create_ambulance_request(user, start_date, end_date, reason):
    """
    Creates an ambulance request and sends notifications.
    """
    ambulance_model = _model_or_none("Ambulance_request")
    if ambulance_model is None:
        raise LookupError("Ambulance_request model not available in current schema")

    user_info = ExtraInfo.objects.get(user=user)
    request_obj = ambulance_model.objects.create(
        user_id=user_info,
        date_request=datetime.now(),
        start_date=start_date,
        end_date=end_date or None,
        reason=reason,
    )

    compounders = ExtraInfo.objects.filter(user_type="compounder")
    healthcare_center_notif(user, user, "amb_request", "")
    for compounder in compounders:
        healthcare_center_notif(user, compounder.user, "amb_req", "")
    return request_obj


def create_appointment(user, doctor_id, date_str, description):
    """
    Uses get_schedule_for_appointment, creates Appointment, sends notifications.
    """
    appointment_model = _model_or_none("Appointment")
    if appointment_model is None:
        raise LookupError("Appointment model not available in current schema")

    try:
        schedule = get_schedule_for_appointment(doctor_id, date_str)
    except ScheduleNotFound:
        raise

    user_info = ExtraInfo.objects.get(user=user)
    doctor = Doctor.objects.get(pk=doctor_id)
    appointment = appointment_model.objects.create(
        user_id=user_info,
        doctor_id=doctor,
        description=description,
        schedule=schedule,
        date=datetime.strptime(date_str, "%Y-%m-%d").date(),
    )

    compounders = ExtraInfo.objects.filter(user_type="compounder")
    healthcare_center_notif(user, user, "appoint", "")
    for compounder in compounders:
        healthcare_center_notif(user, compounder.user, "appoint_req", "")
    return appointment


def cancel_ambulance_request(pk):
    ambulance_model = _model_or_none("Ambulance_request")
    if ambulance_model is None:
        raise LookupError("Ambulance_request model not available in current schema")
    ambulance_model.objects.filter(pk=pk).delete()


def cancel_appointment(pk):
    appointment_model = _model_or_none("Appointment")
    if appointment_model is None:
        raise LookupError("Appointment model not available in current schema")
    appointment_model.objects.filter(pk=pk).delete()


def create_complaint(user, complaint_text):
    complaint_model = _model_or_none("HealthCenterFeedback") or _model_or_none("Complaint")
    if complaint_model is None:
        raise LookupError("Complaint model not available in current schema")
    user_info = ExtraInfo.objects.get(user=user)
    return complaint_model.objects.create(user_id=user_info, complaint=complaint_text)


def respond_complaint(complaint_id, feedback):
    complaint_model = _model_or_none("HealthCenterFeedback") or _model_or_none("Complaint")
    if complaint_model is None:
        raise LookupError("Complaint model not available in current schema")
    complaint_model.objects.filter(pk=complaint_id).update(feedback=feedback)


def add_doctor(data):
    return Doctor.objects.create(**data)


def deactivate_doctor(doctor_id):
    Doctor.objects.filter(pk=doctor_id).update(active=False)


def add_pathologist(data):
    return Pathologist.objects.create(**data)


def deactivate_pathologist(pathologist_id):
    Pathologist.objects.filter(pk=pathologist_id).update(active=False)


def upsert_doctor_schedule(doctor_id, day, from_time, to_time, room):
    doctor = Doctor.objects.get(pk=doctor_id)
    schedule = Doctors_Schedule.objects.filter(doctor_id=doctor, day=day).first()
    if schedule is None:
        return Doctors_Schedule.objects.create(
            doctor_id=doctor,
            day=day,
            from_time=from_time,
            to_time=to_time,
            room=room,
        )
    schedule.from_time = from_time
    schedule.to_time = to_time
    schedule.room = room
    schedule.save(update_fields=["from_time", "to_time", "room"])
    return schedule


def delete_doctor_schedule(doctor_id, day):
    Doctors_Schedule.objects.filter(doctor_id=doctor_id, day=day).delete()


def upsert_pathologist_schedule(pathologist_id, day, from_time, to_time, room):
    pathologist = Pathologist.objects.get(pk=pathologist_id)
    schedule = Pathologist_Schedule.objects.filter(pathologist_id=pathologist, day=day).first()
    if schedule is None:
        return Pathologist_Schedule.objects.create(
            pathologist_id=pathologist,
            day=day,
            from_time=from_time,
            to_time=to_time,
            room=room,
        )
    schedule.from_time = from_time
    schedule.to_time = to_time
    schedule.room = room
    schedule.save(update_fields=["from_time", "to_time", "room"])
    return schedule


def delete_pathologist_schedule(pathologist_id, day):
    Pathologist_Schedule.objects.filter(pathologist_id=pathologist_id, day=day).delete()


def add_medicine(data):
    return All_Medicine.objects.create(**data)


def add_stock(medicine_id, quantity, supplier, expiry_date):
    medicine = All_Medicine.objects.get(pk=medicine_id)
    stock_entry = Stock_entry.objects.create(
        medicine_id=medicine,
        quantity=quantity,
        supplier=supplier,
        Expiry_date=expiry_date,
    )
    present_stock = Present_Stock.objects.create(
        medicine_id=medicine,
        stock_id=stock_entry,
        quantity=quantity,
        Expiry_date=expiry_date,
    )
    return stock_entry, present_stock


def submit_prescription(data):
    return All_Prescription.objects.create(**data)


def add_prescribed_medicine(data):
    return All_Prescribed_medicine.objects.create(**data)


def create_medical_relief(description, uploaded_file):
    return medical_relief.objects.create(description=description, file=uploaded_file)
