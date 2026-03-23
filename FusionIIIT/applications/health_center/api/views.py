import logging

from django.http import Http404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    AllMedicineSerializer,
    AllPrescribedMedicineSerializer,
    AllPrescriptionSerializer,
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
    add_prescribed_medicine,
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

logger = logging.getLogger(__name__)


def get_designations(user):
    return get_designations_for_user(user)


def ensure_compounder_access(request):
    if "Compounder" not in get_designations(request.user):
        raise PermissionError("Compounder role required")


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def student_dashboard_api(request):
    data = get_student_dashboard_data(request.user)
    response_payload = {
        "user_info": data["user_info"].id,
        "doctors": DoctorSerializer(data["doctors"], many=True).data,
        "pathologists": PathologistSerializer(data["pathologists"], many=True).data,
        "doctor_schedule": DoctorsScheduleSerializer(data["doctor_schedule"], many=True).data,
        "pathologist_schedule": PathologistScheduleSerializer(data["pathologist_schedule"], many=True).data,
        "prescriptions": AllPrescriptionSerializer(data["prescriptions"], many=True).data,
        "prescribed_medicines": AllPrescribedMedicineSerializer(data["prescribed_medicines"], many=True).data,
        "stock": StockEntrySerializer([s.stock_id for s in data["stock"]], many=True).data,
    }
    return Response(response_payload, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def compounder_dashboard_api(request):
    try:
        ensure_compounder_access(request)
    except PermissionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

    data = get_compounder_dashboard_data()
    response_payload = {
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
    return Response(response_payload, status=status.HTTP_200_OK)


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


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_doctor_api(request):
    ensure_compounder_access(request)
    serializer = DoctorSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    doctor = add_doctor(serializer.validated_data)
    return Response(DoctorSerializer(doctor).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_doctor_api(request, pk):
    ensure_compounder_access(request)
    deactivate_doctor(pk)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_pathologist_api(request):
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


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def submit_prescription_api(request):
    ensure_compounder_access(request)
    serializer = AllPrescriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    prescription = submit_prescription(serializer.validated_data)
    return Response(AllPrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


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

    prescribed = add_prescribed_medicine(serializer.validated_data)
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
