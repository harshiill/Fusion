import base64
import logging
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from collections import defaultdict

from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
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
from ..models import (
    All_Medicine,
    All_Prescribed_medicine,
    All_Prescription,
    Doctor,
    Doctors_Schedule,
    Pathologist,
    Present_Stock,
    Required_medicine,
    Stock_entry,
    files,
)
from applications.globals.models import ExtraInfo
from applications.hr2.models import EmpDependents
from django.contrib.auth.models import User
from ..models import Announcement, MedicalRelief, MedicalProfile, Pathologist_Schedule, medical_relief
from applications.filetracking.sdk.methods import view_inbox

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

DAY_INDEX_BY_NAME = {value.lower(): key for key, value in DAY_NAME_BY_INDEX.items()}


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


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_day_value(day_value):
    if day_value is None:
        return None

    day_int = _safe_int(day_value, None)
    if day_int is not None and day_int in DAY_NAME_BY_INDEX:
        return day_int

    day_text = str(day_value).strip().lower()
    return DAY_INDEX_BY_NAME.get(day_text)


def _normalize_time_value(value):
    if value in [None, ""]:
        return None
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return value

    value = str(value).strip()
    for fmt in ["%H:%M", "%H:%M:%S"]:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError("Invalid time format. Expected HH:MM")


def _normalize_date_value(value):
    if value in [None, ""]:
        return None
    if isinstance(value, date):
        return value

    value = str(value).strip()
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid date format")


def _extract_trailing_id(value):
    if value is None:
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return None

    direct = _safe_int(text, None)
    if direct is not None:
        return direct

    if "," in text:
        return _safe_int(text.split(",")[-1].strip(), None)

    return None


def _decode_base64_content(raw_value):
    if raw_value in [None, ""]:
        return None

    content = str(raw_value)
    if "," in content:
        content = content.split(",", 1)[1]

    try:
        return base64.b64decode(content)
    except Exception:
        logger.exception("Failed to decode base64 content")
        return None


def _read_excel_rows(file_base64):
    file_bytes = _decode_base64_content(file_base64)
    if not file_bytes:
        return []

    try:
        import pandas as pd

        dataframe = pd.read_excel(BytesIO(file_bytes))
        dataframe = dataframe.where(dataframe.notna(), None)
        return dataframe.to_dict(orient="records")
    except Exception:
        logger.exception("Failed to parse uploaded excel file")
        return []


def _pick_row_value(row, aliases, default=None):
    normalized_row = {}
    for key, value in row.items():
        normalized_key = str(key).strip().lower().replace(" ", "_")
        normalized_row[normalized_key] = value

    for alias in aliases:
        if alias in normalized_row and normalized_row[alias] not in [None, ""]:
            return normalized_row[alias]
    return default


def _resolve_doctor(value):
    if value in [None, ""]:
        return None
    doctor_id = _extract_trailing_id(value)
    if doctor_id is not None:
        doctor = Doctor.objects.filter(id=doctor_id, active=True).first()
        if doctor:
            return doctor

    doctor_name = str(value).strip()
    return Doctor.objects.filter(doctor_name__iexact=doctor_name, active=True).first()


def _resolve_pathologist(value):
    if value in [None, ""]:
        return None
    pathologist_id = _extract_trailing_id(value)
    if pathologist_id is not None:
        pathologist = Pathologist.objects.filter(id=pathologist_id, active=True).first()
        if pathologist:
            return pathologist

    pathologist_name = str(value).strip()
    return Pathologist.objects.filter(pathologist_name__iexact=pathologist_name, active=True).first()


def _resolve_medicine(value):
    if value in [None, ""]:
        return None

    medicine_id = _extract_trailing_id(value)
    if medicine_id is not None:
        medicine = All_Medicine.objects.filter(id=medicine_id).first()
        if medicine:
            return medicine

    medicine_name = str(value).split(",")[0].strip()
    return All_Medicine.objects.filter(brand_name__iexact=medicine_name).first()


def _store_binary_file(raw_base64):
    content = _decode_base64_content(raw_base64)
    if not content:
        return 0
    uploaded = files.objects.create(file_data=content)
    return uploaded.id


def _serialize_workflow_relief(relief):
    status_value = str(relief.status or "").upper()
    is_forwarded = status_value in {
        MedicalRelief.STATUS_PHC_REVIEWED,
        MedicalRelief.STATUS_ACCOUNTS_REVIEWED,
        MedicalRelief.STATUS_SANCTIONED,
        MedicalRelief.STATUS_PAID,
    }
    is_approved = status_value in {
        MedicalRelief.STATUS_ACCOUNTS_REVIEWED,
        MedicalRelief.STATUS_SANCTIONED,
        MedicalRelief.STATUS_PAID,
    }
    is_rejected = status_value == MedicalRelief.STATUS_REJECTED

    uploader = "Unknown"
    if getattr(relief, "user_id", None) and getattr(relief.user_id, "user", None):
        uploader = relief.user_id.user.username

    return {
        "id": relief.id,
        "uploader": uploader,
        "upload_date": relief.created_at.date().isoformat() if relief.created_at else "",
        "approval_date": relief.updated_at.date().isoformat() if relief.updated_at else "",
        "desc": relief.description,
        "file": relief.file.name if relief.file else "",
        "status": is_forwarded,
        "status1": is_approved,
        "status2": is_rejected,
    }


def _build_legacy_prescription_list(prescriptions, page, search_text, page_size=10, response_key="report_prescriptions", pages_key="total_pages_prescriptions"):
    rows = list(prescriptions)

    if search_text:
        query = str(search_text).strip().lower()
        filtered_rows = []
        for presc in rows:
            doctor_name = presc.doctor_id.doctor_name if presc.doctor_id else ""
            haystack = " ".join(
                [
                    str(presc.user_id or ""),
                    str(doctor_name),
                    str(presc.date or ""),
                    str(presc.details or ""),
                ]
            ).lower()
            if query in haystack:
                filtered_rows.append(presc)
        rows = filtered_rows

    total_pages = max(1, (len(rows) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    report = []
    for presc in rows[start:end]:
        report.append(
            {
                "id": presc.id,
                "user_id": presc.user_id,
                "doctor_id": presc.doctor_id.doctor_name if presc.doctor_id else "N/A",
                "date": presc.date,
                "details": presc.details,
                "dependent_name": presc.dependent_name,
                "file_id": presc.file_id,
            }
        )

    return {
        response_key: report,
        pages_key: total_pages,
    }


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
                "user_id": presc.user_id,
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


def _build_legacy_stock_report(stock_rows, page, search_text, response_key, page_size=10):
    stock_rows = list(stock_rows)

    if search_text:
        query = str(search_text).strip().lower()
        filtered_rows = []
        for stock in stock_rows:
            medicine_name = stock.medicine_id.brand_name if stock.medicine_id else ""
            haystack = " ".join(
                [
                    str(medicine_name),
                    str(stock.supplier or ""),
                    str(stock.Expiry_date or ""),
                ]
            ).lower()
            if query in haystack:
                filtered_rows.append(stock)
        stock_rows = filtered_rows

    total_pages = max(1, (len(stock_rows) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    current = stock_rows[start:end]

    report = []
    for stock in current:
        stock_quantity = (
            Present_Stock.objects.filter(stock_id=stock).values_list("quantity", flat=True).first() or 0
        )
        report.append(
            {
                "id": stock.id,
                "medicine_id": stock.medicine_id.brand_name if stock.medicine_id else "N/A",
                "supplier": stock.supplier,
                "Expiry_date": stock.Expiry_date,
                "quantity": stock_quantity,
            }
        )

    return {
        response_key: report,
        "page_stock_view": page,
        "page_stock_expired": page,
        "total_pages_stock_view": total_pages,
        "total_pages_stock_expired": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page_number": page - 1 if page > 1 else None,
        "next_page_number": page + 1 if page < total_pages else None,
    }


def _build_legacy_feedback_payload():
    # Legacy complaint model may not exist in the current schema.
    return {"complaints": []}


def _build_legacy_relief_payload(username):
    relief_items = []

    # Backward compatibility with legacy medical_relief + filetracking flow.
    try:
        inbox_files = view_inbox(username=username, designation="Compounder", src_module="health_center")
    except Exception:
        logger.exception("Unable to fetch compounder inbox for legacy medical relief")
        inbox_files = []

    relief_map = {row.file_id: row for row in medical_relief.objects.all()}

    for item in inbox_files:
        file_id = item.get("id")
        try:
            file_id = int(file_id)
        except (TypeError, ValueError):
            continue

        relief_row = relief_map.get(file_id)
        if relief_row is None:
            continue

        relief_items.append(
            {
                "id": file_id,
                "uploader": item.get("uploader"),
                "upload_date": item.get("upload_date"),
                "desc": relief_row.description,
                "file": f"file-{file_id}",
                "status": bool(relief_row.compounder_forward_flag),
                "status1": bool(relief_row.acc_admin_forward_flag),
                "status2": False,
            }
        )

    # New MedicalRelief workflow support so new student submissions are visible in legacy pages.
    for row in MedicalRelief.objects.select_related("user_id", "user_id__user").all().order_by("-created_at"):
        serialized = _serialize_workflow_relief(row)
        if any(existing.get("id") == serialized["id"] for existing in relief_items):
            continue
        relief_items.append(serialized)

    return {"relief": relief_items}


def _build_legacy_relief_application_payload(username, file_id):
    payload = _build_legacy_relief_payload(username)
    for item in payload["relief"]:
        if item["id"] == file_id:
            return {"inbox": item}
    return {"inbox": None}


def _build_legacy_prescription_detail(data, presc_id):
    all_prescriptions = list(data["prescriptions"])
    prescription = next((row for row in all_prescriptions if row.id == presc_id), None)

    if prescription is None:
        return {
            "prescription": {
                "user_id": data["user_info"].id,
                "dependent_name": "SELF",
            },
            "prescriptions": [],
            "not_revoked": [],
        }

    all_prescribed = list(data["prescribed_medicines"])
    root_id = prescription.follow_up_of_id or prescription.id
    related_prescriptions = [
        row for row in all_prescriptions if row.id == root_id or row.follow_up_of_id == root_id
    ]
    related_prescriptions.sort(key=lambda row: (row.date, row.id), reverse=True)

    details = []
    for presc in related_prescriptions:
        medicines = []
        revoked_medicines = []
        for med in all_prescribed:
            if med.prescription_id_id != presc.id:
                continue
            med_obj = {
                "id": med.id,
                "medicine": med.medicine_id.brand_name if med.medicine_id else "N/A",
                "quantity": med.quantity,
                "days": med.days,
                "times": med.times,
                "date": presc.date,
            }
            if med.revoked:
                revoked_medicines.append(med_obj)
            else:
                medicines.append(med_obj)

        details.append(
            {
                "id": presc.id,
                "followUpDate": presc.date,
                "doctor": presc.doctor_id.doctor_name if presc.doctor_id else "N/A",
                "diseaseDetails": presc.details,
                "tests": presc.test,
                "file_id": presc.file_id,
                "revoked_medicines": revoked_medicines,
                "medicines": medicines,
            }
        )

    latest_id = details[0]["id"] if details else prescription.id
    not_revoked = []
    for med in all_prescribed:
        if med.prescription_id_id == latest_id and not med.revoked:
            not_revoked.append(
                {
                    "id": med.id,
                    "medicine": med.medicine_id.brand_name if med.medicine_id else "N/A",
                    "quantity": med.quantity,
                    "days": med.days,
                    "times": med.times,
                }
            )

    return {
        "prescription": {
            "user_id": prescription.user_id,
            "dependent_name": prescription.dependent_name,
        },
        "prescriptions": details,
        "not_revoked": not_revoked,
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

        if _is_legacy_flag_set(payload, "get_medicines"):
            medicines = All_Medicine.objects.all().order_by("brand_name")
            return Response({"medicines": AllMedicineSerializer(medicines, many=True).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "add_doctor"):
            doctor_payload = {
                "doctor_name": (payload.get("new_doctor") or payload.get("doctor_name") or "").strip(),
                "doctor_phone": str(payload.get("phone") or payload.get("doctor_phone") or "").strip(),
                "specialization": (payload.get("specialization") or "").strip(),
                "active": True,
            }
            serializer = DoctorSerializer(data=doctor_payload)
            if not serializer.is_valid():
                return Response({"status": 0, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            doctor = add_doctor(serializer.validated_data)
            return Response({"status": 1, "doctor": DoctorSerializer(doctor).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "remove_doctor"):
            doctor = _resolve_doctor(payload.get("doctor_active") or payload.get("doctor_id"))
            if not doctor:
                return Response({"status": 0, "detail": "Doctor not found"}, status=status.HTTP_404_NOT_FOUND)
            deactivate_doctor(doctor.id)
            return Response({"status": 1, "detail": "Doctor removed"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "add_pathologist"):
            pathologist_payload = {
                "pathologist_name": (payload.get("new_pathologist") or payload.get("pathologist_name") or "").strip(),
                "pathologist_phone": str(payload.get("phone") or payload.get("pathologist_phone") or "").strip(),
                "specialization": (payload.get("specialization") or "").strip(),
                "active": True,
            }
            serializer = PathologistSerializer(data=pathologist_payload)
            if not serializer.is_valid():
                return Response({"status": 0, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            pathologist = add_pathologist(serializer.validated_data)
            return Response({"status": 1, "pathologist": PathologistSerializer(pathologist).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "remove_pathologist"):
            pathologist = _resolve_pathologist(payload.get("pathologist_active") or payload.get("pathologist_id"))
            if not pathologist:
                return Response({"status": 0, "detail": "Pathologist not found"}, status=status.HTTP_404_NOT_FOUND)
            deactivate_pathologist(pathologist.id)
            return Response({"status": 1, "detail": "Pathologist removed"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "edit_1"):
            doctor = _resolve_doctor(payload.get("doctor"))
            day = _normalize_day_value(payload.get("day"))
            room = _safe_int(payload.get("room"), None)
            if not doctor or day is None or room is None:
                return Response({"status": 0, "detail": "Invalid doctor/day/room"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                from_time = _normalize_time_value(payload.get("time_in"))
                to_time = _normalize_time_value(payload.get("time_out"))
                schedule = upsert_doctor_schedule(doctor.id, day, from_time, to_time, room)
            except Exception as exc:
                return Response({"status": 0, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"status": 1, "schedule": DoctorsScheduleSerializer(schedule).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "rmv"):
            doctor = _resolve_doctor(payload.get("doctor"))
            day = _normalize_day_value(payload.get("day"))
            if not doctor or day is None:
                return Response({"status": 0, "detail": "Invalid doctor/day"}, status=status.HTTP_400_BAD_REQUEST)
            delete_doctor_schedule(doctor.id, day)
            return Response({"status": 1, "detail": "Schedule removed"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "edit12"):
            pathologist = _resolve_pathologist(payload.get("pathologist"))
            day = _normalize_day_value(payload.get("day"))
            room = _safe_int(payload.get("room"), None)
            if not pathologist or day is None or room is None:
                return Response({"status": 0, "detail": "Invalid pathologist/day/room"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                from_time = _normalize_time_value(payload.get("time_in"))
                to_time = _normalize_time_value(payload.get("time_out"))
                schedule = upsert_pathologist_schedule(pathologist.id, day, from_time, to_time, room)
            except Exception as exc:
                return Response({"status": 0, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"status": 1, "schedule": PathologistScheduleSerializer(schedule).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "rmv1"):
            pathologist = _resolve_pathologist(payload.get("pathologist"))
            day = _normalize_day_value(payload.get("day"))
            if not pathologist or day is None:
                return Response({"status": 0, "detail": "Invalid pathologist/day"}, status=status.HTTP_400_BAD_REQUEST)
            delete_pathologist_schedule(pathologist.id, day)
            return Response({"status": 1, "detail": "Schedule removed"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_stock"):
            raw_search = payload.get("medicine_name_for_stock")
            selected_medicine_id = _extract_trailing_id(raw_search)
            search_text = str(raw_search or "").split(",")[0].strip()

            query = All_Medicine.objects.all()
            if selected_medicine_id is not None:
                query = query.filter(id=selected_medicine_id)
            elif search_text:
                query = query.filter(brand_name__icontains=search_text)

            similar_rows = list(
                query.order_by("brand_name")[:20].values(
                    "id",
                    "medicine_name",
                    "brand_name",
                    "constituents",
                    "manufacturer_name",
                    "threshold",
                    "pack_size_label",
                )
            )

            stock_rows = []
            if selected_medicine_id is None and len(similar_rows) == 1:
                selected_medicine_id = similar_rows[0]["id"]

            if selected_medicine_id is not None:
                for stock in Present_Stock.objects.select_related("medicine_id").filter(
                    medicine_id_id=selected_medicine_id,
                    quantity__gt=0,
                    Expiry_date__gte=date.today(),
                ).order_by("Expiry_date"):
                    stock_rows.append(
                        {
                            "id": stock.id,
                            "brand_name": stock.medicine_id.brand_name if stock.medicine_id else "N/A",
                            "quantity": stock.quantity,
                            "expiry": stock.Expiry_date,
                        }
                    )

            return Response({"sim": similar_rows, "val": stock_rows}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "add_medicine"):
            medicine_payload = {
                "medicine_name": (payload.get("new_medicine") or payload.get("medicine_name") or payload.get("brand_name") or "").strip(),
                "brand_name": (payload.get("brand_name") or payload.get("new_medicine") or "").strip(),
                "constituents": (payload.get("constituents") or "").strip(),
                "manufacturer_name": (payload.get("manufacture_name") or payload.get("manufacturer_name") or "").strip(),
                "threshold": _safe_int(payload.get("threshold"), 0) or 0,
                "pack_size_label": str(payload.get("packsize") or payload.get("pack_size_label") or "").strip(),
            }
            serializer = AllMedicineSerializer(data=medicine_payload)
            if not serializer.is_valid():
                return Response({"status": 0, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            medicine = add_medicine(serializer.validated_data)
            return Response({"status": 1, "medicine": AllMedicineSerializer(medicine).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "add_medicine_excel"):
            rows = _read_excel_rows(payload.get("file_data"))
            created_count = 0
            for row in rows:
                brand_name = _pick_row_value(row, ["brand_name", "brand", "brandname", "medicine_brand"], "")
                if not brand_name:
                    continue

                defaults = {
                    "medicine_name": _pick_row_value(row, ["medicine_name", "medicine", "name"], brand_name),
                    "constituents": _pick_row_value(row, ["constituents", "composition"], ""),
                    "manufacturer_name": _pick_row_value(row, ["manufacturer_name", "manufacture_name", "manufacturer"], ""),
                    "threshold": _safe_int(_pick_row_value(row, ["threshold", "min_stock"], 0), 0) or 0,
                    "pack_size_label": str(_pick_row_value(row, ["pack_size_label", "packsize", "pack_size"], "")),
                }
                _, created = All_Medicine.objects.get_or_create(brand_name=str(brand_name).strip(), defaults=defaults)
                if created:
                    created_count += 1

            return Response({"status": 1, "created": created_count}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "add_stock"):
            medicine_id = _safe_int(payload.get("medicine_id"), None)
            quantity = _safe_int(payload.get("quantity"), None)
            expiry_date = payload.get("expiry_date") or payload.get("Expiry_date")
            supplier = str(payload.get("supplier") or "NOT_SET").strip() or "NOT_SET"

            if medicine_id is None or quantity is None or quantity <= 0:
                return Response({"status": 0, "detail": "Invalid medicine or quantity"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                expiry_obj = _normalize_date_value(expiry_date)
                if expiry_obj is None:
                    raise ValueError("Expiry date is required")
            except ValueError as exc:
                return Response({"status": 0, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            try:
                stock_entry, _ = add_stock(medicine_id, quantity, supplier, expiry_obj)
            except Exception as exc:
                return Response({"status": 0, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"status": 1, "stock_id": stock_entry.id}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "add_stock_excel"):
            rows = _read_excel_rows(payload.get("file_data"))
            created_count = 0

            for row in rows:
                medicine_id = _safe_int(_pick_row_value(row, ["medicine_id", "id"], None), None)
                brand_name = _pick_row_value(row, ["brand_name", "brand", "medicine"], "")
                quantity = _safe_int(_pick_row_value(row, ["quantity", "qty"], 0), 0) or 0
                supplier = str(_pick_row_value(row, ["supplier", "vendor"], "NOT_SET"))
                expiry_raw = _pick_row_value(row, ["expiry_date", "expiry", "expiry_date_yyyy-mm-dd"], None)

                medicine = All_Medicine.objects.filter(id=medicine_id).first() if medicine_id else None
                if medicine is None and brand_name:
                    medicine = All_Medicine.objects.filter(brand_name__iexact=str(brand_name).strip()).first()
                if medicine is None or quantity <= 0:
                    continue

                try:
                    expiry_date = _normalize_date_value(expiry_raw)
                    if expiry_date is None:
                        continue
                except ValueError:
                    continue

                add_stock(medicine.id, quantity, supplier, expiry_date)
                created_count += 1

            return Response({"status": 1 if created_count > 0 else 0, "created": created_count}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "edit_threshold"):
            medicine_id = _safe_int(payload.get("medicine_id"), None)
            threshold = _safe_int(payload.get("threshold"), None)
            if medicine_id is None or threshold is None:
                return Response({"status": 0, "detail": "Invalid medicine or threshold"}, status=status.HTTP_400_BAD_REQUEST)

            medicine = All_Medicine.objects.filter(id=medicine_id).first()
            if medicine is None:
                return Response({"status": 0, "detail": "Medicine not found"}, status=status.HTTP_404_NOT_FOUND)

            medicine.threshold = threshold
            medicine.save(update_fields=["threshold"])
            return Response({"status": 1, "detail": "Threshold updated"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_file"):
            file_id = _safe_int(payload.get("file_id"), None)
            if file_id == -2:
                path = Path(__file__).resolve().parents[3] / "static" / "health_center" / "add_stock_example.xlsx"
                if not path.exists():
                    return Response({"detail": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
                return FileResponse(open(path, "rb"), as_attachment=True, filename="example_add_stock.xlsx")

            if file_id == -1:
                path = Path(__file__).resolve().parents[3] / "static" / "health_center" / "add_medicine_example.xlsx"
                if not path.exists():
                    return Response({"detail": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
                return FileResponse(open(path, "rb"), as_attachment=True, filename="example_add_medicine.xlsx")

            if file_id is None or file_id <= 0:
                return Response({"detail": "Invalid file id"}, status=status.HTTP_400_BAD_REQUEST)

            file_row = files.objects.filter(id=file_id).first()
            if file_row is None:
                return Response({"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND)

            response = HttpResponse(file_row.file_data, content_type="application/pdf")
            response["Content-Disposition"] = 'inline; filename="generated.pdf"'
            return response

        if payload.get("user_for_dependents") is not None:
            username = str(payload.get("user_for_dependents") or "").strip()
            extra_info = ExtraInfo.objects.select_related("user").filter(user__username=username).first()
            if not extra_info:
                return Response({"status": -1, "dep": []}, status=status.HTTP_200_OK)

            dependents = EmpDependents.objects.filter(extra_info=extra_info)
            dep_payload = [{"name": dep.name, "relation": dep.relationship} for dep in dependents]
            return Response({"status": 1, "dep": dep_payload}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "prescribe_b"):
            patient_username = str(payload.get("user") or "").strip()
            if not patient_username or not User.objects.filter(username=patient_username).exists():
                return Response({"status": -1, "detail": "No patient found"}, status=status.HTTP_200_OK)

            doctor = _resolve_doctor(payload.get("doctor"))
            if doctor is None:
                return Response({"status": 0, "detail": "Invalid doctor"}, status=status.HTTP_400_BAD_REQUEST)

            is_dependent = str(payload.get("is_dependent") or "self").lower() == "dependent"
            dependent_name = str(payload.get("dependent_name") or "SELF").strip() or "SELF"
            dependent_relation = str(payload.get("dependent_relation") or "SELF").strip() or "SELF"
            file_id = _store_binary_file(payload.get("file"))
            medicines = payload.get("pre_medicine") or []

            try:
                with transaction.atomic():
                    prescription = All_Prescription.objects.create(
                        user_id=patient_username,
                        doctor_id=doctor,
                        details=str(payload.get("details") or "").strip(),
                        date=date.today(),
                        suggestions="",
                        test=str(payload.get("tests") or "").strip(),
                        file_id=file_id,
                        is_dependent=is_dependent,
                        dependent_name=dependent_name if is_dependent else "SELF",
                        dependent_relation=dependent_relation if is_dependent else "SELF",
                    )

                    for item in medicines:
                        medicine = _resolve_medicine(item.get("brand_name") or item.get("astock"))
                        quantity = _safe_int(item.get("quantity"), 0) or 0
                        if medicine is None or quantity <= 0:
                            continue

                        result = prescribe_medicine(medicine.id, quantity, prescription.id)
                        if not result.get("success"):
                            raise ValueError(result.get("message") or "Medicine prescription failed")

                        prescribed = result.get("prescribed_medicine")
                        if prescribed:
                            prescribed.days = _safe_int(item.get("Days"), 0) or 0
                            prescribed.times = _safe_int(item.get("Times"), 0) or 0
                            prescribed.save(update_fields=["days", "times"])
            except Exception as exc:
                return Response({"status": 0, "detail": str(exc)}, status=status.HTTP_200_OK)

            return Response({"status": 1, "detail": "Prescription created"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "presc_followup"):
            base_prescription_id = _safe_int(payload.get("pre_id"), None)
            base_prescription = All_Prescription.objects.filter(id=base_prescription_id).first()
            if base_prescription is None:
                return Response({"status": 0, "detail": "Prescription not found"}, status=status.HTTP_404_NOT_FOUND)

            doctor = _resolve_doctor(payload.get("doctor"))
            if doctor is None:
                return Response({"status": 0, "detail": "Invalid doctor"}, status=status.HTTP_400_BAD_REQUEST)

            file_id = _store_binary_file(payload.get("file"))
            revoke_ids = payload.get("revoked") or []
            if isinstance(revoke_ids, str):
                revoke_ids = [revoke_ids]
            medicines = payload.get("pre_medicine") or []

            try:
                with transaction.atomic():
                    followup = All_Prescription.objects.create(
                        user_id=base_prescription.user_id,
                        doctor_id=doctor,
                        details=str(payload.get("details") or "").strip(),
                        date=date.today(),
                        suggestions="",
                        test=str(payload.get("tests") or "").strip(),
                        file_id=file_id,
                        is_dependent=base_prescription.is_dependent,
                        dependent_name=base_prescription.dependent_name,
                        dependent_relation=base_prescription.dependent_relation,
                        follow_up_of=base_prescription.follow_up_of or base_prescription,
                    )

                    for revoke_id in revoke_ids:
                        med_id = _safe_int(revoke_id, None)
                        if med_id is None:
                            continue
                        med_row = All_Prescribed_medicine.objects.filter(id=med_id).first()
                        if med_row:
                            med_row.revoked = True
                            med_row.revoked_date = date.today()
                            med_row.revoked_prescription = followup
                            med_row.save(update_fields=["revoked", "revoked_date", "revoked_prescription"])

                    for item in medicines:
                        medicine = _resolve_medicine(item.get("brand_name") or item.get("astock"))
                        quantity = _safe_int(item.get("quantity"), 0) or 0
                        if medicine is None or quantity <= 0:
                            continue

                        result = prescribe_medicine(medicine.id, quantity, followup.id)
                        if not result.get("success"):
                            raise ValueError(result.get("message") or "Follow-up medicine prescription failed")

                        prescribed = result.get("prescribed_medicine")
                        if prescribed:
                            prescribed.days = _safe_int(item.get("Days"), 0) or 0
                            prescribed.times = _safe_int(item.get("Times"), 0) or 0
                            prescribed.save(update_fields=["days", "times"])
            except Exception as exc:
                return Response({"status": 0, "detail": str(exc)}, status=status.HTTP_200_OK)

            return Response({"status": 1, "detail": "Follow-up created"}, status=status.HTTP_200_OK)

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

        if payload.get("datatype") == "manage_expired_view":
            page = payload.get("page_expired", 1)
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1
            return Response(
                _build_legacy_stock_report(
                    data["expired_stock"],
                    page=page,
                    search_text=payload.get("search_view_expired", ""),
                    response_key="report_stock_expired",
                ),
                status=status.HTTP_200_OK,
            )

        if payload.get("datatype") == "manage_required_view":
            page = payload.get("page_required_view", 1)
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1

            required_rows = list(Required_medicine.objects.select_related("medicine_id").all().order_by("medicine_id__brand_name"))
            query = str(payload.get("search_view_required") or "").strip().lower()
            if query:
                required_rows = [
                    row for row in required_rows if query in str(row.medicine_id.brand_name if row.medicine_id else "").lower()
                ]

            page_size = 10
            total_pages = max(1, (len(required_rows) + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            start = (page - 1) * page_size
            end = start + page_size

            report = []
            for row in required_rows[start:end]:
                report.append(
                    {
                        "id": row.id,
                        "medicine_id": row.medicine_id.brand_name if row.medicine_id else "N/A",
                        "quantity": row.quantity,
                        "threshold": row.threshold,
                    }
                )

            return Response(
                {
                    "report_required": report,
                    "total_pages_required": total_pages,
                    "page_required_view": page,
                },
                status=status.HTTP_200_OK,
            )

        if payload.get("datatype") == "manage_prescriptions_view":
            page = _safe_int(payload.get("page_prescriptions"), 1) or 1
            return Response(
                _build_legacy_prescription_list(
                    data["prescriptions"],
                    page=page,
                    search_text=payload.get("search_prescriptions", ""),
                ),
                status=status.HTTP_200_OK,
            )

        if payload.get("datatype") == "manage_patient_view":
            page = _safe_int(payload.get("page_patient"), 1) or 1
            patient_user = str(payload.get("user_id") or "").strip()
            prescriptions = [row for row in data["prescriptions"] if not patient_user or str(row.user_id) == patient_user]
            return Response(
                _build_legacy_prescription_list(
                    prescriptions,
                    page=page,
                    search_text=payload.get("search_patient", ""),
                    response_key="report_patient",
                    pages_key="total_pages_patient",
                ),
                status=status.HTTP_200_OK,
            )

        if _is_legacy_flag_set(payload, "get_prescription"):
            presc_id = payload.get("presc_id")
            try:
                presc_id = int(presc_id)
            except (TypeError, ValueError):
                presc_id = -1
            return Response(_build_legacy_prescription_detail(data, presc_id), status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_annoucements") or _is_legacy_flag_set(payload, "get_announcements"):
            announcements = Announcement.objects.all().order_by("-ann_date", "-id")
            return Response({"announcements": AnnouncementSerializer(announcements, many=True).data}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_relief"):
            user_info = ExtraInfo.objects.filter(user=request.user).first()
            if not user_info:
                return Response({"relief": []}, status=status.HTTP_200_OK)

            relief_rows = MedicalRelief.objects.select_related("user_id", "user_id__user").filter(user_id=user_info).order_by("-created_at")
            relief_payload = [_serialize_workflow_relief(row) for row in relief_rows]
            return Response({"relief": relief_payload}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "medical_relief_submit"):
            user_info = ExtraInfo.objects.filter(user=request.user).first()
            if not user_info:
                return Response({"status": 0, "detail": "User profile not found"}, status=status.HTTP_400_BAD_REQUEST)

            description = (payload.get("description") or "").strip()
            uploaded_file = payload.get("file")

            # Legacy clients may send base64 directly under file_data.
            if not uploaded_file and payload.get("file_data"):
                file_bytes = _decode_base64_content(payload.get("file_data"))
                if file_bytes:
                    filename = payload.get("filename") or "medical_relief_upload.bin"
                    uploaded_file = ContentFile(file_bytes, name=filename)

            obj = MedicalRelief.objects.create(
                user_id=user_info,
                description=description,
                file=uploaded_file if uploaded_file else None,
            )
            return Response({"status": 1, "id": obj.id, "detail": "Medical relief request submitted"}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "feed_submit"):
            feedback = (payload.get("feedback") or "").strip()
            if not feedback:
                return Response({"status": 0, "detail": "Feedback cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                create_complaint(request.user, feedback)
            except Exception:
                # Complaint model is optional in current schema; keep backward-compatible success.
                logger.info("Complaint model unavailable; accepted feedback without persistence")

            return Response({"status": 1, "detail": "Feedback submitted"}, status=status.HTTP_200_OK)

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

        if payload.get("datatype") == "manage_stock_view":
            page = payload.get("page_stock_view", 1)
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1
            return Response(
                _build_legacy_stock_report(
                    data["live_stock"],
                    page=page,
                    search_text=payload.get("search_view_stock", ""),
                    response_key="report_stock_view",
                ),
                status=status.HTTP_200_OK,
            )

        if payload.get("datatype") == "manage_stock_expired":
            page = payload.get("page_stock_expired", 1)
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1
            return Response(
                _build_legacy_stock_report(
                    data["expired_stock"],
                    page=page,
                    search_text=payload.get("search_view_expired", ""),
                    response_key="report_stock_expired",
                ),
                status=status.HTTP_200_OK,
            )

        if _is_legacy_flag_set(payload, "get_feedback"):
            return Response(_build_legacy_feedback_payload(), status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_relief"):
            return Response(_build_legacy_relief_payload(request.user.username), status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "get_application"):
            file_id = payload.get("aid")
            try:
                file_id = int(file_id)
            except (TypeError, ValueError):
                file_id = -1
            return Response(
                _build_legacy_relief_application_payload(request.user.username, file_id),
                status=status.HTTP_200_OK,
            )

        if _is_legacy_flag_set(payload, "compounder_forward"):
            file_id = payload.get("file_id")
            try:
                file_id = int(file_id)
            except (TypeError, ValueError):
                return Response({"detail": "Invalid file_id", "status": 0}, status=status.HTTP_400_BAD_REQUEST)

            row = medical_relief.objects.filter(file_id=file_id).first()
            if row is not None:
                row.compounder_forward_flag = True
                row.save(update_fields=["compounder_forward_flag"])
                return Response({"detail": "Forwarded", "status": 1}, status=status.HTTP_200_OK)

            workflow_row = MedicalRelief.objects.filter(id=file_id).first()
            if workflow_row is None:
                return Response({"detail": "Medical relief request not found", "status": 0}, status=status.HTTP_404_NOT_FOUND)

            workflow_row.status = MedicalRelief.STATUS_PHC_REVIEWED
            reviewer = ExtraInfo.objects.filter(user=request.user).first()
            workflow_row.reviewed_by = reviewer
            workflow_row.save(update_fields=["status", "reviewed_by", "updated_at"])
            return Response({"detail": "Forwarded", "status": 1}, status=status.HTTP_200_OK)

        if _is_legacy_flag_set(payload, "compounder_reject"):
            file_id = payload.get("file_id")
            try:
                file_id = int(file_id)
            except (TypeError, ValueError):
                return Response({"detail": "Invalid file_id", "status": 0}, status=status.HTTP_400_BAD_REQUEST)

            row = medical_relief.objects.filter(file_id=file_id).first()
            if row is not None:
                row.compounder_forward_flag = False
                row.save(update_fields=["compounder_forward_flag"])
                return Response({"detail": "Rejected", "status": 1}, status=status.HTTP_200_OK)

            workflow_row = MedicalRelief.objects.filter(id=file_id).first()
            if workflow_row is None:
                return Response({"detail": "Medical relief request not found", "status": 0}, status=status.HTTP_404_NOT_FOUND)

            workflow_row.status = MedicalRelief.STATUS_REJECTED
            reviewer = ExtraInfo.objects.filter(user=request.user).first()
            workflow_row.reviewed_by = reviewer
            workflow_row.save(update_fields=["status", "reviewed_by", "updated_at"])
            return Response({"detail": "Rejected", "status": 1}, status=status.HTTP_200_OK)

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
        profile = MedicalProfile.objects.filter(user_id=user_info).first()
        if profile:
            serializer = MedicalProfileSerializer(profile, data=payload, partial=True)
            serializer.is_valid(raise_exception=True)
            profile = serializer.save()
            return Response(MedicalProfileSerializer(profile).data, status=status.HTTP_200_OK)

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
