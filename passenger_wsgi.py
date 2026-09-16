import os
import sys
import glob

# 1. Project root
PROJECT_ROOT = '/home/acrmate1/hotelerp.acrmatech.com'
sys.path.insert(0, PROJECT_ROOT)

# 2. Dynamically find the virtual environment's site-packages path
# This prevents errors if Python 3.10, 3.11, 3.12 or 3.13 is selected.
VENV_ROOT = '/home/acrmate1/virtualenv/hotelerp.acrmatech.com'
site_packages_pattern = os.path.join(VENV_ROOT, '**/lib/python*/site-packages')
found_dirs = glob.glob(site_packages_pattern, recursive=True)

if found_dirs:
    sys.path.insert(1, found_dirs[0])
else:
    # Fallback to default if glob fails
    sys.path.insert(1, '/home/acrmate1/virtualenv/hotelerp.acrmatech.com/3.13/lib/python3.13/site-packages')

# 3. Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_production')

# 4. Start WSGI application with error reporting
try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception:
    import logging
    logging.exception("Django failed to start under Passenger.")
    def application(environ, start_response):
        status = '500 Internal Server Error'
        output = b"Application failed to start. Check the server error log."
        response_headers = [('Content-type', 'text/plain'), ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]
