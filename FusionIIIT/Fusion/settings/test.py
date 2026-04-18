from Fusion.settings.common import *

DEBUG = False
TEMPLATE_DEBUG = False
SECRET_KEY = 'test-secret-key'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django_crontab',
    'corsheaders',
    'applications.eis',
    'notification',
    'applications.academic_procedures',
    'applications.examination',
    'applications.academic_information',
    'applications.leave',
    'applications.library',
    'applications.notifications_extension',
    'applications.gymkhana',
    'applications.office_module',
    'applications.globals',
    'applications.central_mess',
    'applications.complaint_system',
    'applications.filetracking',
    'applications.finance_accounts',
    'applications.health_center',
    'applications.online_cms',
    'applications.ps1',
    'applications.programme_curriculum',
    'applications.placement_cell',
    'applications.otheracademic',
    'applications.recruitment',
    'applications.scholarships',
    'applications.visitor_hostel',
    'applications.establishment',
    'applications.estate_module',
    'applications.counselling_cell',
    'applications.hostel_management',
    'applications.research_procedures',
    'applications.income_expenditure',
    'applications.hr2',
    'applications.department',
    'applications.iwdModuleV2',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'semanticuiforms',
    'applications.feeds.apps.FeedsConfig',
    'pagedown',
    'markdown_deux',
    'django_cleanup.apps.CleanupConfig',
    'django_unused_media',
    'rest_framework',
    'rest_framework.authtoken',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'test_db.sqlite3'),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

MIGRATION_MODULES = {
    'academic_information': None,
    'academic_procedures': None,
    'central_mess': None,
    'complaint_system': None,
    'counselling_cell': None,
    'department': None,
    'eis': None,
    'establishment': None,
    'estate_module': None,
    'examination': None,
    'filetracking': None,
    'finance_accounts': None,
    'globals': None,
    'gymkhana': None,
    'health_center': None,
    'hostel_management': None,
    'hr2': None,
    'income_expenditure': None,
    'iwdModuleV2': None,
    'leave': None,
    'library': None,
    'notification': None,
    'notifications_extension': None,
    'office_module': None,
    'online_cms': None,
    'otheracademic': None,
    'placement_cell': None,
    'programme_curriculum': None,
    'placement_cell': None,
    'ps1': None,
    'recruitment': None,
    'research_procedures': None,
    'scholarships': None,
    'feeds': None,
    'visitor_hostel': None,
}
