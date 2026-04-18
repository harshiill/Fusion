"""Fusion URL Configuration."""

from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, re_path

IS_TEST_SETTINGS = getattr(settings, 'SETTINGS_MODULE', '').endswith('.test')

if not IS_TEST_SETTINGS:
    import debug_toolbar

    from applications.globals.views import RateLimitedPasswordResetView


if IS_TEST_SETTINGS:
    urlpatterns = [
        re_path(r'^admin/', admin.site.urls),
        re_path(r'^', include(('applications.globals.test_urls', 'globals'), namespace='globals')),
        re_path(r'^healthcenter/', include('applications.health_center.urls')),
    ]
else:
    urlpatterns = [
        re_path(r'^', include('applications.globals.urls')),
        re_path(r'^feeds/', include('applications.feeds.urls')),
        re_path(r'^admin/', admin.site.urls),
        re_path(r'^academic-procedures/', include('applications.academic_procedures.urls')),
        re_path(r'^aims/', include('applications.academic_information.urls')),
        re_path(r'^notifications/', include('applications.notifications_extension.urls')),
        re_path(r'^estate/', include('applications.estate_module.urls')),
        re_path(r'^dep/', include('applications.department.urls')),
        re_path(r'^programme_curriculum/',include('applications.programme_curriculum.urls')),
        re_path(r'^iwdModuleV2/', include('applications.iwdModuleV2.urls')),
        re_path(r'^__debug__/', include(debug_toolbar.urls)),
        re_path(r'^research_procedures/', include('applications.research_procedures.urls')),
        re_path(r'^accounts/', include('allauth.urls')),


        re_path(r'^eis/', include('applications.eis.urls')),
        re_path(r'^mess/', include('applications.central_mess.urls')),
        re_path(r'^complaint/', include('applications.complaint_system.urls')),
        re_path(r'^healthcenter/', include('applications.health_center.urls')),
        re_path(r'^leave/', include('applications.leave.urls')),
        re_path(r'^placement/', include('applications.placement_cell.urls')),
        re_path(r'^filetracking/', include('applications.filetracking.urls')),
        re_path(r'^spacs/', include('applications.scholarships.urls')),
        re_path(r'^visitorhostel/', include('applications.visitor_hostel.urls')),
        re_path(r'^office/', include('applications.office_module.urls')),
        re_path(r'^finance/', include('applications.finance_accounts.urls')),
        re_path(r'^purchase-and-store/', include('applications.ps1.urls')),
        re_path(r'^gymkhana/', include('applications.gymkhana.urls')),
        re_path(r'^library/', include('applications.library.urls')),
        re_path(r'^establishment/', include('applications.establishment.urls')),
        re_path(r'^ocms/', include('applications.online_cms.urls')),
        re_path(r'^counselling/', include('applications.counselling_cell.urls')),
        re_path(r'^hostelmanagement/', include('applications.hostel_management.urls')),
        re_path(r'^income-expenditure/', include('applications.income_expenditure.urls')),
        re_path(r'^hr2/', include('applications.hr2.urls')),
        re_path(r'^recruitment/', include('applications.recruitment.urls')),
        re_path(r'^examination/', include('applications.examination.urls')),
        re_path(r'^otheracademic/', include('applications.otheracademic.urls')),

        path(
            'password-reset/',
            RateLimitedPasswordResetView.as_view(
                template_name='registration/password_reset_form.html',
            ),
            name='reset_password',
        ),
        path(
            'password-reset/done/',
            auth_views.PasswordResetDoneView.as_view(
                template_name='registration/password_reset_done.html'
            ),
            name='password_reset_done',
        ),
        path(
            'reset/<uidb64>/<token>/',
            auth_views.PasswordResetConfirmView.as_view(
                template_name='registration/password_reset_confirm.html',
            ),
            name='password_reset_confirm',
        ),
        path(
            'reset/done/',
            auth_views.PasswordResetCompleteView.as_view(
                template_name='registration/password_reset_complete.html'
            ),
            name='password_reset_complete',
        ),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
