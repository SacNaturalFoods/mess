# Django settings for the Mess project.

import os

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
)

MANAGERS = ADMINS

DATABASE_ENGINE = 'postgresql_psycopg2' # 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = 'mess'                  # Or path to database file if using sqlite3.
DATABASE_USER = 'mess'                  # Not used with sqlite3.
DATABASE_PASSWORD = 'caGlisjem6'        # Not used with sqlite3.
DATABASE_HOST = 'localhost'          # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''                      # Set to empty string for default. Not used with sqlite3.


TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the root of the project.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# URL of the project.  Leave out a network address to keep links relative.
# Make sure to use a trailing slash.
PROJECT_URL = '/mess/'

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media/')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = PROJECT_URL + 'media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = PROJECT_URL + '/admin/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '4w-cz*to=zc-gjoqtrf=pi2m54i@ghqlnsdq=2mq7e^8fbgh#w'

# Application and model that stores user profiles.
AUTH_PROFILE_MODULE = 'people.Person'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

ROOT_URLCONF = 'mess.urls'

LOCATION = 'Cashier'

TEMPLATE_DIRS = (
    PROJECT_ROOT + '/templates',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    #'django.contrib.sites',
    'django.contrib.admin',
    'mess.accounting',
    'mess.contact',
    'mess.membership',
    'mess.people',
    'mess.work',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'mess.context_processors.project',
)

