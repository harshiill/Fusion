from django.conf.urls import url

from . import views

urlpatterns = [
    url(r"^student/$", views.student_legacy_api, name="student_legacy_api"),
    url(r"^compounder/$", views.compounder_legacy_api, name="compounder_legacy_api"),

    url(r"^student/dashboard/$", views.student_dashboard_api, name="student_dashboard_api"),
    url(r"^compounder/dashboard/$", views.compounder_dashboard_api, name="compounder_dashboard_api"),

    url(r"^ambulances/$", views.create_ambulance_request_api, name="create_ambulance_request_api"),
    url(r"^ambulances/(?P<pk>[0-9]+)/$", views.cancel_ambulance_request_api, name="cancel_ambulance_request_api"),
    url(r"^appointments/$", views.create_appointment_api, name="create_appointment_api"),
    url(r"^appointments/(?P<pk>[0-9]+)/$", views.cancel_appointment_api, name="cancel_appointment_api"),
    url(r"^complaints/$", views.create_complaint_api, name="create_complaint_api"),
    url(r"^complaints/respond/$", views.respond_complaint_api, name="respond_complaint_api"),
    url(
        r"^complaints/(?P<complaint_id>[0-9]+)/respond/$",
        views.respond_complaint_detail_api,
        name="respond_complaint_detail_api",
    ),

    url(r"^doctors/$", views.add_doctor_api, name="add_doctor_api"),
    url(r"^doctors/(?P<doctor_id>[0-9]+)/schedule/$", views.doctor_schedule_api, name="doctor_schedule_api"),
    url(r"^doctors/(?P<pk>[0-9]+)/$", views.remove_doctor_api, name="remove_doctor_api"),
    url(r"^pathologists/$", views.add_pathologist_api, name="add_pathologist_api"),
    url(r"^pathologist-schedules/list/$", views.pathologist_schedule_list_api, name="pathologist_schedule_list_api"),
    url(r"^pathologists/(?P<pk>[0-9]+)/$", views.remove_pathologist_api, name="remove_pathologist_api"),

    url(r"^doctor-schedules/$", views.upsert_doctor_schedule_api, name="upsert_doctor_schedule_api"),
    url(r"^schedules/$", views.schedule_api, name="schedule_api"),
    url(
        r"^doctor-schedules/(?P<doctor_id>[0-9]+)/(?P<day>[0-9]+)/$",
        views.remove_doctor_schedule_api,
        name="remove_doctor_schedule_api",
    ),
    url(r"^pathologist-schedules/$", views.upsert_pathologist_schedule_api, name="upsert_pathologist_schedule_api"),
    url(
        r"^pathologist-schedules/(?P<pathologist_id>[0-9]+)/(?P<day>[0-9]+)/$",
        views.remove_pathologist_schedule_api,
        name="remove_pathologist_schedule_api",
    ),

    url(r"^medicines/$", views.add_medicine_api, name="add_medicine_api"),
    url(r"^medicines/required/$", views.required_medicines_api, name="required_medicines_api"),
    url(r"^stocks/$", views.add_stock_api, name="add_stock_api"),
    url(r"^stock-entries/$", views.add_stock_api, name="stock_entries_api"),
    url(r"^prescriptions/$", views.submit_prescription_api, name="submit_prescription_api"),
    url(
        r"^prescriptions/(?P<prescription_id>[0-9]+)/followup/$",
        views.prescription_followup_api,
        name="prescription_followup_api",
    ),
    url(r"^prescribed-medicines/$", views.add_prescribed_medicine_api, name="add_prescribed_medicine_api"),
    url(r"^announcements/$", views.announcement_api, name="announcement_api"),
    url(r"^medical-relief/$", views.medical_relief_api, name="medical_relief_api"),
    url(r"^medical-relief/(?P<relief_id>[0-9]+)/review/$", views.medical_relief_review_api, name="medical_relief_review_api"),
    url(r"^medical-profile/$", views.medical_profile_api, name="medical_profile_api"),
    url(r"^patients/$", views.patient_search_api, name="patient_search_api"),

    url(r"^hospital-admits/$", views.admit_patient_api, name="admit_patient_api"),
    url(r"^hospital-admits/(?P<pk>[0-9]+)/discharge/$", views.discharge_patient_api, name="discharge_patient_api"),
]