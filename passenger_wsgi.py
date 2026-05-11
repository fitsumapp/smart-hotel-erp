import os
import sys

# 1. Project root
PROJECT_ROOT = '/home/acrmate1/hotelerp.acrmatech.com'
sys.path.insert(0, PROJECT_ROOT)

# 2. Virtual environment site-packages
VENV_PACKAGES = '/home/acrmate1/virtualenv/hotelerp.acrmatech.com/3.13/lib/python3.13/site-packages'
sys.path.insert(1, VENV_PACKAGES)

# 3. Django settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'

# 4. Start WSGI application with error reporting
try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception as e:
    error_msg = str(e)
    import traceback
    tb = traceback.format_exc()
    def application(environ, start_response):
        status = '500 Internal Server Error'
        output = f"Error: {error_msg}\n\nTraceback:\n{tb}\n\nPython Path: {sys.path}".encode()
        response_headers = [('Content-type', 'text/plain'), ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]
