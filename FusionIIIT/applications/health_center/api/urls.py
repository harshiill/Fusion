from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^student/$", views.student_legacy_api, name="student_legacy_api"),
    re_path(r"^compounder/$", views.compounder_legacy_api, name="compounder_legacy_api"),

    re_path(r"^student/dashboard/$", views.student_dashboard_api, name="student_dashboard_api"),
    re_path(r"^compounder/dashboard/$", views.compounder_dashboard_api, name="compounder_dashboard_api"),

    re_path(r"^ambulances/$", views.create_ambulance_request_api, name="create_ambulance_request_api"),
    re_path(r"^ambulances/(?P<pk>[0-9]+)/$", views.cancel_ambulance_request_api, name="cancel_ambulance_request_api"),
    re_path(r"^appointments/$", views.create_appointment_api, name="create_appointment_api"),
    re_path(r"^appointments/(?P<pk>[0-9]+)/$", views.cancel_appointment_api, name="cancel_appointment_api"),
    re_path(r"^complaints/$", views.create_complaint_api, name="create_complaint_api"),
    re_path(r"^complaints/respond/$", views.respond_complaint_api, name="respond_complaint_api"),
    re_path(
        r"^complaints/(?P<complaint_id>[0-9]+)/respond/$",
        views.respond_complaint_detail_api,
        name="respond_complaint_detail_api",
    ),

    re_path(r"^doctors/$", views.add_doctor_api, name="add_doctor_api"),
    re_path(r"^doctors/(?P<doctor_id>[0-9]+)/schedule/$", views.doctor_schedule_api, name="doctor_schedule_api"),
    re_path(r"^doctor-attendance/$", views.doctor_attendance_api, name="doctor_attendance_api"),
    re_path(r"^doctors/(?P<pk>[0-9]+)/$", views.remove_doctor_api, name="remove_doctor_api"),
    re_path(r"^pathologists/$", views.add_pathologist_api, name="add_pathologist_api"),
    re_path(r"^pathologist-schedules/list/$", views.pathologist_schedule_list_api, name="pathologist_schedule_list_api"),
    re_path(r"^pathologists/(?P<pk>[0-9]+)/$", views.remove_pathologist_api, name="remove_pathologist_api"),

    re_path(r"^doctor-schedules/$", views.upsert_doctor_schedule_api, name="upsert_doctor_schedule_api"),
    re_path(r"^schedules/$", views.schedule_api, name="schedule_api"),
    re_path(
        r"^doctor-schedules/(?P<doctor_id>[0-9]+)/(?P<day>[0-9]+)/$",
        views.remove_doctor_schedule_api,
        name="remove_doctor_schedule_api",
    ),
    re_path(r"^pathologist-schedules/$", views.upsert_pathologist_schedule_api, name="upsert_pathologist_schedule_api"),
    re_path(
        r"^pathologist-schedules/(?P<pathologist_id>[0-9]+)/(?P<day>[0-9]+)/$",
        views.remove_pathologist_schedule_api,
        name="remove_pathologist_schedule_api",
    ),

    re_path(r"^medicines/$", views.add_medicine_api, name="add_medicine_api"),
    re_path(r"^medicines/required/$", views.required_medicines_api, name="required_medicines_api"),
    re_path(r"^stocks/$", views.add_stock_api, name="add_stock_api"),
    re_path(r"^stock-entries/$", views.add_stock_api, name="stock_entries_api"),
    re_path(r"^prescriptions/$", views.submit_prescription_api, name="submit_prescription_api"),
    re_path(
        r"^prescriptions/(?P<prescription_id>[0-9]+)/followup/$",
        views.prescription_followup_api,
        name="prescription_followup_api",
    ),
    re_path(r"^prescribed-medicines/$", views.add_prescribed_medicine_api, name="add_prescribed_medicine_api"),
    re_path(r"^announcements/$", views.announcement_api, name="announcement_api"),
    re_path(r"^medical-relief/$", views.medical_relief_api, name="medical_relief_api"),
    re_path(r"^medical-relief/(?P<relief_id>[0-9]+)/review/$", views.medical_relief_review_api, name="medical_relief_review_api"),
    re_path(r"^medical-profile/$", views.medical_profile_api, name="medical_profile_api"),
    re_path(r"^patients/$", views.patient_search_api, name="patient_search_api"),

    re_path(r"^hospital-admits/$", views.admit_patient_api, name="admit_patient_api"),
    re_path(r"^hospital-admits/(?P<pk>[0-9]+)/discharge/$", views.discharge_patient_api, name="discharge_patient_api"),
]