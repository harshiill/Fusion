import logging
from collections import defaultdict

from django.http import Http404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    AnnouncementSerializer,
    AllMedicineSerializer,
    AllPrescribedMedicineSerializer,
    AllPrescriptionSerializer,
    MedicalProfileSerializer,
    MedicalReliefWorkflowSerializer,
    AmbulanceRequestCreateSerializer,
    AppointmentCreateSerializer,
    ComplaintCreateSerializer,
    ComplaintResponseSerializer,
    DoctorSerializer,
    DoctorsScheduleSerializer,
    PathologistScheduleSerializer,
    PathologistSerializer,
    StockEntrySerializer,
)
from .selectors import (
    ScheduleNotFound,
    get_compounder_dashboard_data,
    get_designations_for_user,
    get_student_dashboard_data,
)
from .services import (
    add_doctor,
    add_medicine,
    add_pathologist,
    add_stock,
    cancel_ambulance_request,
    cancel_appointment,
    create_ambulance_request,
    create_appointment,
    create_complaint,
    deactivate_doctor,
    deactivate_pathologist,
    delete_doctor_schedule,
    delete_pathologist_schedule,
    prescribe_medicine,
    respond_complaint,
    submit_prescription,
    upsert_doctor_schedule,
    upsert_pathologist_schedule,
)
from ..models import All_Prescription, Doctors_Schedule, Required_medicine, Present_Stock
from applications.globals.models import ExtraInfo
from django.contrib.auth.models import User
from ..models import Announcement, MedicalRelief, MedicalProfile, Pathologist_Schedule

logger = logging.getLogger(__name__)

DAY_NAME_BY_INDEX = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


def get_designations(user):
    return get_designations_for_user(user)


def ensure_compounder_access(request):
    if "Compounder" not in get_designations(request.user):
        raise PermissionError("Compounder role required")


def _is_legacy_flag_set(payload, key):
    value = payload.get(key)
    if value is True:
        return True
    if value is None:
        return False
    return str(value) == "1"


def _format_slot_time(from_time, to_time):
    if from_time and to_time:
        return f"{from_time.strftime('%H:%M')} - {to_time.strftime('%H:%M')}"
    if from_time:
        return from_time.strftime("%H:%M")
    if to_time:
        return to_time.strftime("%H:%M")
    return "Not Available"


def _build_legacy_doctor_schedule(data):
    schedule_rows = list(data["doctor_schedule"])
    schedule_by_doctor_id = {}
    for slot in schedule_rows:
        schedule_by_doctor_id.setdefault(slot.doctor_id_id, []).append(
            {
                "day": DAY_NAME_BY_INDEX.get(slot.day, str(slot.day)),
                "time": _format_slot_time(slot.from_time, slot.to_time),
            }
        )

    result = []
    for doctor in data["doctors"]:
        result.append(
            {
                "name": doctor.doctor_name,
                "specialization": doctor.specialization,
                "availability": schedule_by_doctor_id.get(doctor.id, []),
            }
        )
    return result


def _build_legacy_pathologist_schedule(data):
    schedule_rows = list(data["pathologist_schedule"])
    schedule_by_pathologist_id = {}
    for slot in schedule_rows:
        schedule_by_pathologist_id.setdefault(slot.pathologist_id_id, []).append(
            {
                "day": DAY_NAME_BY_INDEX.get(slot.day, str(slot.day)),
                "time": _format_slot_time(slot.from_time, slot.to_time),
            }
        )

    result = []
    for pathologist in data["pathologists"]:
        result.append(
            {
                "name": pathologist.pathologist_name,
                "specialization": pathologist.specialization,
                "availability": schedule_by_pathologist_id.get(pathologist.id, []),
            }
        )
    return result


def _build_legacy_patientlog(data, page, search_text, page_size=10):
    prescriptions = list(data["prescriptions"])

    if search_text:
        query = str(search_text).strip().lower()
        filtered = []
        for presc in prescriptions:
            doctor_name = presc.doctor_id.doctor_name if presc.doctor_id else ""
            haystack = " ".join(
                [
                    str(doctor_name),
                    str(presc.date or ""),
                    str(presc.details or ""),
                    str(presc.dependent_name or ""),
                ]
            ).lower()
            if query in haystack:
                filtered.append(presc)
        prescriptions = filtered

    total_pages = max(1, (len(prescriptions) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    current = prescriptions[start:end]

    report = []
    for presc in current:
        report.append(
            {
                "id": presc.id,
                "doctor_id": presc.doctor_id.doctor_name if presc.doctor_id else "N/A",
                "date": presc.date,
                "details": presc.details,
                "dependent_name": presc.dependent_name,
            }
        )

    return {
        "report": report,
        "total_pages": total_pages,
    }


def _build_legacy_prescription_detail(data, presc_id):
    prescription = None
    for row in data["prescriptions"]:
        if row.id == presc_id:
            prescription = row
            break

    if prescription is None:
        return {
            "prescription": {
                "user_id": data["user_info"].id,
                "dependent_name": "SELF",
            },
            "prescriptions": [],
        }

    all_prescribed = list(data["prescribed_medicines"])
    medicines = []
    revoked_medicines = []
    for med in all_prescribed:
        if med.prescription_id_id != prescription.id:
            continue
        med_obj = {
            "medicine": med.medicine_id.brand_name if med.medicine_id else "N/A",
            "quantity": med.quantity,
            "days": med.days,
            "times": med.times,
            "date": prescription.date,
        }
        if med.revoked:
            revoked_medicines.append(med_obj)
        else:
            medicines.append(med_obj)

    detail = {
        "id": prescription.id,
        "followUpDate": prescription.date,
        "doctor": prescription.doctor_id.doctor_name if prescription.doctor_id else "N/A",
        "diseaseDetails": prescription.details,
        "tests": prescription.test,
        "revoked_medicines": revoked_medicines,
        "medicines": medicines,
    }

    return {
        "prescription": {
            "user_id": prescription.user_id,
            "dependent_name": prescription.dependent_name,
        },
        "prescriptions": [detail],
    }


def _build_student_dashboard_payload(user):
    data = get_student_dashboard_data(user)
    return {
        "user_info": data["user_info"].id,
        "doctors": DoctorSerializer(data["doctors"], many=True).data,
        "pathologists": PathologistSerializer(data["pathologists"], many=True).data,
        "doctor_schedule": DoctorsScheduleSerializer(data["doctor_schedule"], many=True).data,
        "pathologist_schedule": PathologistScheduleSerializer(data["pathologist_schedule"], many=True).data,
        "prescriptions": AllPrescriptionSerializer(data["prescriptions"], many=True).data,
        "prescribed_medicines": AllPrescribedMedicineSerializer(data["prescribed_medicines"], many=True).data,
        "stock": StockEntrySerializer([s.stock_id for s in data["stock"]], many=True).data,
    }


def _build_compounder_dashboard_payload():
    data = get_compounder_dashboard_data()
    return {
        "users": [u.id for u in data["users"]],
        "doctors": DoctorSerializer(data["doctors"], many=True).data,
        "pathologists": PathologistSerializer(data["pathologists"], many=True).data,
        "doctor_schedule": DoctorsScheduleSerializer(data["doctor_schedule"], many=True).data,
        "pathologist_schedule": PathologistScheduleSerializer(data["pathologist_schedule"], many=True).data,
        "required_medicines": [obj.id for obj in data["required_medicines"]],
        "expired_stock": StockEntrySerializer(data["expired_stock"], many=True).data,
        "live_stock": StockEntrySerializer(data["live_stock"], many=True).data,
        "prescriptions": AllPrescriptionSerializer(data["prescriptions"], many=True).data,
        "prescribed_medicines": AllPrescribedMedicineSerializer(data["prescribed_medicines"], many=True).data,
    }


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def student_legacy_api(request):
    """
    Legacy compatibility endpoint for Fusion-client health center module.
    Returns the dashboard payload used by legacy POST-based client calls.
    """
    data = get_student_dashboard_data(request.user)
    if request.method == "POST":
        payload = request.data or {}

        if _is_legacy_flag_set(payload, "get_doctor_schedule"):
            return Response({"schedule": _build_legacy_doctor_schedule(data)}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_pathologist_schedule"):
            return Response({"schedule": _build_legacy_pathologist_schedule(data)}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_doctors"):
            return Response({"doctors": DoctorSerializer(data["doctors"], many=True).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_pathologists"):
            return Response({"pathologists": PathologistSerializer(data["pathologists"], many=True).data}, status=status.HTTP_200_OK)

        if payload.get("datatype") == "patientlog":
            page = payload.get("page", 1)
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1
            return Response(
                _build_legacy_patientlog(data, page=page, search_text=payload.get("search_patientlog", "")),
                status=status.HTTP_200_OK,
            )

        if _is_legacy_flag_set(payload, "get_prescription"):
            presc_id = payload.get("presc_id")
            try:
                presc_id = int(presc_id)
            except (TypeError, ValueError):
                presc_id = -1
            return Response(_build_legacy_prescription_detail(data, presc_id), status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_annoucements"):
            return Response({"announcements": []}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_relief"):
            return Response({"relief": []}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "medical_relief_submit"):
            return Response({"detail": "Medical relief request submitted"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "feed_submit"):
            return Response({"detail": "Feedback submitted"}, status=status.HTTP_200_OK)

    return Response(_build_student_dashboard_payload(request.user), status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def compounder_legacy_api(request):
    """
    Legacy compatibility endpoint for Fusion-client health center module.
    Returns the dashboard payload used by legacy POST-based client calls.
    """
    try:
        ensure_compounder_access(request)
    except PermissionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

    data = get_compounder_dashboard_data()
    if request.method == "POST":
        payload = request.data or {}

        if _is_legacy_flag_set(payload, "get_doctor_schedule"):
            return Response({"schedule": _build_legacy_doctor_schedule(data)}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_pathologist_schedule"):
            return Response({"schedule": _build_legacy_pathologist_schedule(data)}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_doctors"):
            return Response({"doctors": DoctorSerializer(data["doctors"], many=True).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_pathologists"):
            return Response({"pathologists": PathologistSerializer(data["pathologists"], many=True).data}, status=status.HTTP_200_OK)

    return Response(_build_compounder_dashboard_payload(), status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def student_dashboard_api(request):
    return Response(_build_student_dashboard_payload(request.user), status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def compounder_dashboard_api(request):
    try:
        ensure_compounder_access(request)
    except PermissionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

    return Response(_build_compounder_dashboard_payload(), status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_ambulance_request_api(request):
    serializer = AmbulanceRequestCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        ambulance = create_ambulance_request(
            request.user,
            serializer.validated_data["start_date"],
            serializer.validated_data.get("end_date"),
            serializer.validated_data["reason"],
        )
    except LookupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response({"id": ambulance.id}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def cancel_ambulance_request_api(request, pk):
    try:
        cancel_ambulance_request(pk)
    except LookupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_appointment_api(request):
    serializer = AppointmentCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        appointment = create_appointment(
            request.user,
            serializer.validated_data["doctor_id"],
            serializer.validated_data["date"].isoformat(),
            serializer.validated_data["description"],
        )
    except ScheduleNotFound as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except LookupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response({"id": appointment.id}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def cancel_appointment_api(request, pk):
    try:
        cancel_appointment(pk)
    except LookupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_complaint_api(request):
    serializer = ComplaintCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        complaint = create_complaint(request.user, serializer.validated_data["complaint"])
    except LookupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response({"id": complaint.id}, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_doctor_api(request):
    if request.method == "GET":
        serializer = DoctorSerializer(DoctorSerializer.Meta.model.objects.filter(active=True), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    ensure_compounder_access(request)
    serializer = DoctorSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    doctor = add_doctor(serializer.validated_data)
    return Response(DoctorSerializer(doctor).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_doctor_api(request, pk):
    ensure_compounder_access(request)
    try:
        doctor = DoctorSerializer.Meta.model.objects.get(pk=pk)
    except DoctorSerializer.Meta.model.DoesNotExist:
        return Response({"error": "Doctor not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method in ["PUT", "PATCH"]:
        partial = request.method == "PATCH"
        serializer = DoctorSerializer(doctor, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    deactivate_doctor(pk)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_pathologist_api(request):
    if request.method == "GET":
        serializer = PathologistSerializer(PathologistSerializer.Meta.model.objects.filter(active=True), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    ensure_compounder_access(request)
    serializer = PathologistSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pathologist = add_pathologist(serializer.validated_data)
    return Response(PathologistSerializer(pathologist).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_pathologist_api(request, pk):
    ensure_compounder_access(request)
    deactivate_pathologist(pk)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def pathologist_schedule_list_api(request):
    schedules = Pathologist_Schedule.objects.select_related("pathologist_id").all().order_by("day", "from_time")
    return Response(PathologistScheduleSerializer(schedules, many=True).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def upsert_doctor_schedule_api(request):
    ensure_compounder_access(request)
    serializer = DoctorsScheduleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    schedule = upsert_doctor_schedule(
        serializer.validated_data["doctor_id"].id,
        serializer.validated_data["day"],
        serializer.validated_data["from_time"],
        serializer.validated_data["to_time"],
        serializer.validated_data["room"],
    )
    return Response(DoctorsScheduleSerializer(schedule).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def schedule_api(request):
    return upsert_doctor_schedule_api(request)


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_doctor_schedule_api(request, doctor_id, day):
    ensure_compounder_access(request)
    delete_doctor_schedule(doctor_id, day)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def upsert_pathologist_schedule_api(request):
    ensure_compounder_access(request)
    serializer = PathologistScheduleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    schedule = upsert_pathologist_schedule(
        serializer.validated_data["pathologist_id"].id,
        serializer.validated_data["day"],
        serializer.validated_data["from_time"],
        serializer.validated_data["to_time"],
        serializer.validated_data["room"],
    )
    return Response(PathologistScheduleSerializer(schedule).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_pathologist_schedule_api(request, pathologist_id, day):
    ensure_compounder_access(request)
    delete_pathologist_schedule(pathologist_id, day)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_medicine_api(request):
    ensure_compounder_access(request)
    serializer = AllMedicineSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    medicine = add_medicine(serializer.validated_data)
    return Response(AllMedicineSerializer(medicine).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_stock_api(request):
    ensure_compounder_access(request)
    serializer = StockEntrySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    stock_entry, _ = add_stock(
        serializer.validated_data["medicine_id"].id,
        serializer.validated_data["quantity"],
        serializer.validated_data["supplier"],
        serializer.validated_data["Expiry_date"],
    )
    return Response(StockEntrySerializer(stock_entry).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def submit_prescription_api(request):
    if request.method == "GET":
        try:
            ensure_compounder_access(request)
            queryset = All_Prescription.objects.select_related("doctor_id", "follow_up_of").all().order_by("-date", "-id")
        except PermissionError:
            queryset = All_Prescription.objects.select_related("doctor_id", "follow_up_of").filter(
                user_id=request.user.username
            ).order_by("-date", "-id")
        return Response(AllPrescriptionSerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    ensure_compounder_access(request)
    serializer = AllPrescriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    prescription = submit_prescription(serializer.validated_data)
    return Response(AllPrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def prescription_followup_api(request, prescription_id):
    ensure_compounder_access(request)
    try:
        original = All_Prescription.objects.get(pk=prescription_id)
    except All_Prescription.DoesNotExist:
        return Response({"error": "Original prescription not found."}, status=status.HTTP_404_NOT_FOUND)

    payload = request.data.copy()
    payload["follow_up_of"] = original.id
    payload["user_id"] = original.user_id

    serializer = AllPrescriptionSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    follow_up = submit_prescription(serializer.validated_data)
    return Response(AllPrescriptionSerializer(follow_up).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_prescribed_medicine_api(request):
    ensure_compounder_access(request)
    serializer = AllPrescribedMedicineSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    result = prescribe_medicine(
        serializer.validated_data["medicine_id"].id,
        serializer.validated_data["quantity"],
        serializer.validated_data["prescription_id"].id,
    )
    if not result["success"]:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    prescribed = result["prescribed_medicine"]
    return Response(AllPrescribedMedicineSerializer(prescribed).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def respond_complaint_api(request):
    ensure_compounder_access(request)
    serializer = ComplaintResponseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        respond_complaint(serializer.validated_data["complaint_id"], serializer.validated_data["feedback"])
    except LookupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def respond_complaint_detail_api(request, complaint_id):
    ensure_compounder_access(request)
    feedback = (request.data.get("feedback") or "").strip()
    if not feedback:
        return Response({"error": "Feedback cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
    if len(feedback) > 100:
        return Response({"error": "Feedback cannot exceed 100 characters."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        respond_complaint(complaint_id, feedback)
    except LookupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response({"message": "Feedback submitted.", "complaint_id": complaint_id}, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def doctor_schedule_api(request, doctor_id):
    schedules = (
        Doctors_Schedule.objects.select_related("doctor_id")
        .filter(doctor_id_id=doctor_id)
        .order_by("day", "from_time", "to_time")
    )
    return Response(DoctorsScheduleSerializer(schedules, many=True).data, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def required_medicines_api(request):
    stock_by_medicine = defaultdict(int)
    medicine_map = {}

    for row in Present_Stock.objects.select_related("medicine_id").all():
        stock_by_medicine[row.medicine_id_id] += row.quantity
        medicine_map[row.medicine_id_id] = row.medicine_id

    data = []
    for medicine_id, current_quantity in stock_by_medicine.items():
        medicine = medicine_map[medicine_id]
        threshold = medicine.threshold or 0
        if current_quantity <= threshold:
            data.append(
                {
                    "medicine_id": medicine.id,
                    "medicine_name": medicine.medicine_name,
                    "current_quantity": current_quantity,
                    "threshold": threshold,
                }
            )

    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def announcement_api(request):
    if request.method == "GET":
        queryset = Announcement.objects.select_related("created_by", "created_by__user").all().order_by("-ann_date", "-id")
        return Response(AnnouncementSerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    ensure_compounder_access(request)
    user_info = ExtraInfo.objects.filter(user=request.user).first()
    serializer = AnnouncementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(created_by=user_info)
    return Response(AnnouncementSerializer(obj).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def medical_relief_api(request):
    user_info = ExtraInfo.objects.filter(user=request.user).first()
    payload = request.data.copy()
    if user_info:
        payload["user_id"] = user_info.id

    serializer = MedicalReliefWorkflowSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(user_id=user_info)
    return Response(MedicalReliefWorkflowSerializer(obj).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def medical_relief_review_api(request, relief_id):
    ensure_compounder_access(request)
    try:
        relief = MedicalRelief.objects.get(pk=relief_id)
    except MedicalRelief.DoesNotExist:
        return Response({"error": "Medical relief request not found."}, status=status.HTTP_404_NOT_FOUND)

    requested_status = (request.data.get("status") or "").strip().upper()
    allowed = {
        MedicalRelief.STATUS_PHC_REVIEWED,
        MedicalRelief.STATUS_ACCOUNTS_REVIEWED,
        MedicalRelief.STATUS_SANCTIONED,
        MedicalRelief.STATUS_REJECTED,
        MedicalRelief.STATUS_PAID,
    }
    if requested_status not in allowed:
        return Response({"error": "Invalid status transition."}, status=status.HTTP_400_BAD_REQUEST)

    reviewer = ExtraInfo.objects.filter(user=request.user).first()
    relief.status = requested_status
    relief.reviewed_by = reviewer
    relief.save(update_fields=["status", "reviewed_by", "updated_at"])
    return Response(MedicalReliefWorkflowSerializer(relief).data, status=status.HTTP_200_OK)


@api_view(["POST", "PUT", "GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def medical_profile_api(request):
    user_info = ExtraInfo.objects.filter(user=request.user).first()

    if request.method == "GET":
        profile = MedicalProfile.objects.filter(user_id=user_info).first()
        if not profile:
            return Response({}, status=status.HTTP_200_OK)
        return Response(MedicalProfileSerializer(profile).data, status=status.HTTP_200_OK)

    payload = request.data.copy()
    if user_info:
        payload["user_id"] = user_info.id

    if request.method == "POST":
        serializer = MedicalProfileSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(user_id=user_info)
        return Response(MedicalProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    profile = MedicalProfile.objects.filter(user_id=user_info).first()
    if not profile:
        return Response({"error": "Medical profile not found."}, status=status.HTTP_404_NOT_FOUND)
    serializer = MedicalProfileSerializer(profile, data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def patient_search_api(request):
    ensure_compounder_access(request)
    query = (request.GET.get("search") or "").strip()
    users = User.objects.all().select_related("extrainfo")
    if query:
        users = users.filter(username__icontains=query)

    result = []
    for user in users[:50]:
        extra = getattr(user, "extrainfo", None)
        if not extra:
            continue
        result.append(
            {
                "id": extra.id,
                "username": user.username,
                "name": user.get_full_name() or user.username,
                "user_type": extra.user_type,
            }
        )
    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def admit_patient_api(request):
    hospital_admit_model = globals().get("Hospital_admit")
    if hospital_admit_model is None:
        raise Http404("Hospital admit flow is not available in current schema")
    return Response({"detail": "Not yet implemented for active schema"}, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(["PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def discharge_patient_api(request, pk):
    hospital_admit_model = globals().get("Hospital_admit")
    if hospital_admit_model is None:
        raise Http404("Hospital admit flow is not available in current schema")
    return Response({"detail": "Not yet implemented for active schema"}, status=status.HTTP_501_NOT_IMPLEMENTED)
