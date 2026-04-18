"""
Health Center Test Base Configuration
======================================

Codebase findings:
  - Module URLs: /healthcenter/ (legacy template views) and /healthcenter/api/v1/ (API)
  - Models: Doctor, Pathologist, All_Medicine, Stock_entry, Present_Stock, All_Prescription, 
            All_Prescribed_medicine, MedicalRelief (new workflow model), Doctors_Schedule, 
            Pathologist_Schedule, Announcement, MedicalProfile
  - Auth: Template views use @login_required + session['currentDesignationSelected'] for role checks
  - Auth: API views use @api_view, TokenAuthentication, ensure_compounder_access() for PHC staff role
  - User types: ExtraInfo.user_type in ('student', 'staff', 'compounder', 'faculty')
  - Designations: Designation model with names like 'Compounder', 'director', etc.
  - Key foreign keys: Prescription.user_id is CharField(max_length=15), not FK — design constraint

Role mapping:
  - Patient (Student): ExtraInfo.user_type='student', no special designation
  - PHC Staff (Compounder): ExtraInfo.user_type='compounder' OR HoldsDesignation with 'Compounder'
  - Employee: ExtraInfo.user_type='staff' (for reimbursement eligibility)
  - Authority: ExtraInfo.user_type='staff' with 'director' or equivalent designation
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date, timedelta
import json


class BaseHealthCenterTestCase(TestCase):
    """
    Base class for all Health Center tests.
    Sets up users, roles, and common helpers.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test users, roles, and designations."""
        # ── USERS ──────────────────────────────────────────────────────
        cls.patient_user = User.objects.create_user(
            username='2021bcs001', password='testpass123', email='patient@test.com'
        )
        cls.phc_staff_user = User.objects.create_user(
            username='phcstaff01', password='testpass123', email='staff@test.com'
        )
        cls.employee_user = User.objects.create_user(
            username='emp001', password='testpass123', email='emp@test.com'
        )
        cls.authority_user = User.objects.create_user(
            username='auth001', password='testpass123', email='auth@test.com'
        )

        # ── EXTRAINFO (ExtraInfo required by Fusion) ────────────────────
        try:
            from applications.globals.models import ExtraInfo, HoldsDesignation, Designation, DepartmentInfo

            # Create department
            dept, _ = DepartmentInfo.objects.get_or_create(name='Computer Science')

            # Patient (student)
            cls.patient_extra = ExtraInfo.objects.create(
                id='2021bcs001',
                user=cls.patient_user,
                user_type='student',
                department=dept
            )
            
            # PHC Staff (compounder)
            cls.staff_extra = ExtraInfo.objects.create(
                id='phcstaff01',
                user=cls.phc_staff_user,
                user_type='compounder',
                department=dept
            )
            
            # Employee (staff)
            cls.employee_extra = ExtraInfo.objects.create(
                id='emp001',
                user=cls.employee_user,
                user_type='staff',
                department=dept
            )
            
            # Authority (staff with director designation)
            cls.authority_extra = ExtraInfo.objects.create(
                id='auth001',
                user=cls.authority_user,
                user_type='staff',
                department=dept
            )

            # PHC Staff designation
            phc_desig, _ = Designation.objects.get_or_create(
                name='Compounder',
                defaults={'full_name': 'PHC Compounder', 'type': 'administrative'}
            )
            HoldsDesignation.objects.get_or_create(
                user=cls.phc_staff_user,
                working=cls.phc_staff_user,
                designation=phc_desig
            )

            # Authority designation
            auth_desig, _ = Designation.objects.get_or_create(
                name='director',
                defaults={'full_name': 'Director', 'type': 'administrative'}
            )
            HoldsDesignation.objects.get_or_create(
                user=cls.authority_user,
                working=cls.authority_user,
                designation=auth_desig
            )

        except Exception as e:
            print(f"[WARN] ExtraInfo setup failed: {e}. Adjust conftest.py based on models.")

        # ── STUDENT (if required) ──────────────────────────────────────
        try:
            from applications.academic_information.models import Student
            cls.student = Student.objects.create(
                id=cls.patient_extra,
                programme='B.Tech',
                batch=2021
            )
        except Exception as e:
            print(f"[WARN] Student setup failed: {e}")

        # ── CORE HEALTH CENTER DATA ────────────────────────────────────
        try:
            from applications.health_center.models import (
                Doctor, Pathologist, All_Medicine, Stock_entry, Present_Stock
            )
            from datetime import datetime, timedelta

            # Create sample doctor
            cls.doctor = Doctor.objects.create(
                doctor_name='Dr. Smith',
                doctor_phone='9876543210',
                specialization='General Medicine',
                active=True
            )

            # Create sample pathologist
            cls.pathologist = Pathologist.objects.create(
                pathologist_name='Dr. PathTest',
                pathologist_phone='9876543211',
                specialization='Pathology',
                active=True
            )

            # Create sample medicine
            cls.medicine = All_Medicine.objects.create(
                medicine_name='Paracetamol',
                brand_name='Crocin',
                constituents='500mg',
                manufacturer_name='GSK',
                threshold=5,
                pack_size_label='10 tablets'
            )

            # Create stock entry
            expiry_date = date.today() + timedelta(days=365)
            cls.stock_entry = Stock_entry.objects.create(
                medicine_id=cls.medicine,
                quantity=100,
                supplier='Medical Supplier Inc',
                Expiry_date=expiry_date
            )

            # Create present stock
            cls.present_stock = Present_Stock.objects.create(
                medicine_id=cls.medicine,
                stock_id=cls.stock_entry,
                quantity=100,
                Expiry_date=expiry_date
            )

        except Exception as e:
            print(f"[WARN] Health center data setup failed: {e}")

        try:
            from applications.health_center.models import files

            cls.sample_file = files.objects.create(file_data=b'test')
        except Exception as e:
            print(f"[WARN] Sample file setup failed: {e}")

    def setUp(self):
        # Allow client requests to return HTTP 500 instead of raising exceptions,
        # so exception-path tests can assert response status codes.
        self.client.raise_request_exception = False

    # ── AUTH HELPERS ───────────────────────────────────────────────────

    def login_as_patient(self):
        """Login as student/patient user."""
        self.client.force_login(self.patient_user)
        session = self.client.session
        session['currentDesignationSelected'] = 'student'
        session.save()

    def login_as_phc_staff(self):
        """Login as PHC staff/compounder user."""
        self.client.force_login(self.phc_staff_user)
        session = self.client.session
        session['currentDesignationSelected'] = 'Compounder'
        session.save()

    def login_as_employee(self):
        """Login as employee/staff user."""
        self.client.force_login(self.employee_user)
        session = self.client.session
        session['currentDesignationSelected'] = 'staff'
        session.save()

    def login_as_authority(self):
        """Login as authority/director user."""
        self.client.force_login(self.authority_user)
        session = self.client.session
        session['currentDesignationSelected'] = 'director'
        session.save()

    def logout(self):
        """Logout current user."""
        self.client.logout()

    # ── DATE HELPERS ───────────────────────────────────────────────────

    def future_date(self, days=7):
        """Return a date string N days in the future (YYYY-MM-DD)."""
        return (date.today() + timedelta(days=days)).strftime('%Y-%m-%d')

    def past_date(self, days=7):
        """Return a date string N days in the past (YYYY-MM-DD)."""
        return (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')

    def today(self):
        """Return today's date string (YYYY-MM-DD)."""
        return date.today().strftime('%Y-%m-%d')

    # ── REQUEST HELPERS ────────────────────────────────────────────────

    def api_get(self, url, expected_status=200):
        """Execute GET request and assert status."""
        response = self.client.get(url, HTTP_ACCEPT='application/json')
        if expected_status:
            self.assertEqual(response.status_code, expected_status,
                             f"GET {url} expected {expected_status}, got {response.status_code}")
        return response

    def api_post(self, url, data=None, expected_status=200):
        """Execute POST request with JSON data."""
        response = self.client.post(url, data=json.dumps(data or {}),
                                    content_type='application/json')
        if expected_status:
            self.assertEqual(response.status_code, expected_status,
                             f"POST {url} expected {expected_status}, got {response.status_code}")
        return response

    def api_post_form(self, url, data=None):
        """Execute POST for Django form-based views (not REST)."""
        return self.client.post(url, data=data or {}, follow=True)

    def try_json(self, response):
        """Safely parse JSON response, return {} on failure."""
        try:
            return response.json()
        except Exception:
            return {}
