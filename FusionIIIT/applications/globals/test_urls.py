from django.http import HttpResponse
from django.urls import re_path

app_name = 'globals'


def _ok(_request):
    return HttpResponse('ok')


urlpatterns = [
    re_path(r'^$', _ok, name='index'),
    re_path(r'^dashboard/$', _ok, name='dashboard'),
    re_path(r'^about/$', _ok, name='about'),
    re_path(r'^profile/$', _ok, name='profile'),
    re_path(r'^profile/(?P<username>.+)/$', _ok, name='profile'),
    re_path(r'^search/$', _ok, name='search'),
    re_path(r'^feedback/$', _ok, name='feedback'),
    re_path(r'^issue/$', _ok, name='issue'),
    re_path(r'^logout/$', _ok, name='logout_view'),
]
