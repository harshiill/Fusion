from django.conf.urls import include
from django.urls import re_path

from . import views

app_name = 'globals'

urlpatterns = [

    re_path(r'^$', views.index, name='index'),
    re_path(r'^dashboard/$', views.dashboard, name='dashboard'),
    re_path(r'^about/', views.about, name='about'),
    # generic profile endpoint, displays or redirects appropriately
    re_path(r'^profile/(?P<username>.+)/$', views.profile, name='profile'),
    # profile of currently logged user
    re_path(r'^profile/$', views.profile, name='profile'),
    re_path(r'^search/$', views.search, name='search'),
    # Feedback and issues url
    re_path(r'^feedback/$', views.feedback, name="feedback"),
    re_path(r'^issue/$', views.issue, name="issue"),
    re_path(r'^view_issue/(?P<id>\d+)/$', views.view_issue, name="view_issue"),
    re_path(r'^support_issue/(?P<id>\d+)/$', views.support_issue, name="support_issue"),
    re_path(r'^logout/$', views.logout_view, name="logout_view"),
    # Endpoint to reset all passwords in DEV environment
    re_path(r'^resetallpass/$', views.reset_all_pass, name='resetallpass'),
    # API urls
    re_path(r'^api/', include('applications.globals.api.urls')),
    re_path(r'^update_global_variable/$', views.update_global_variable, name='update_global_var'),
]
