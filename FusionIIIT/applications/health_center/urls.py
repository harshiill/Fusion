from django import views
from django.conf.urls import include
from django.urls import re_path

from .views import *

app_name = 'healthcenter'

urlpatterns = [

    # health_center home page
    re_path(r'^$', healthcenter, name='healthcenter'),

    #views
    re_path(r'^compounder/view_prescription/(?P<prescription_id>[0-9]+)/$',compounder_view_prescription,name='view_prescription'),
    re_path(r'^compounder/view_file/(?P<file_id>[\w-]+)/$',view_file, name='view_file'),
    re_path(r'^compounder/$', compounder_view, name='compounder_view'),
    re_path(r'^student/$', student_view, name='student_view'),
    re_path(r'announcement/', announcement, name='announcement'),
    re_path(r'medical_profile/', medical_profile, name='medical_profile'),

    # api (v1 + backward-compatible legacy prefix)
    re_path(r'^api/v1/', include('applications.health_center.api.urls')),
    re_path(r'^api/', include('applications.health_center.api.urls'))
]