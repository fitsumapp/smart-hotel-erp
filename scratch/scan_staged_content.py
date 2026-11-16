import subprocess
import re

print("Running security scan on staged Git diff with file association...")
diff_output = subprocess.check_output(['git', 'diff', '--cached']).decode('utf-8', errors='replace')

PATTERNS = [
    (r'(?i)secret[_-]?key\s*[:=]\s*["\']([^"\']+)["\']', "Potential Secret Key"),
    (r'(?i)api[_-]?key\s*[:=]\s*["\']([^"\']+)["\']', "Potential API Key"),
    (r'-----BEGIN [A-Z ]+ PRIVATE KEY-----', "Private Key Block"),
    (r'postgres(ql)?:\/\/[^:]+:[^@]+@', "Database URI with Password"),
    (r'(?i)password\s*[:=]\s*["\'](?!django_test_dummy)([^"\']+)["\']', "Hardcoded Password")
]

SAFE_SUBSTRINGS = [
    'django-insecure',
    'test-secret',
    'SECRET_KEY_FALLBACK_FOR_TESTS_ONLY',
    'get_env_variable',
    'os.environ',
    'process.env',
    'password123',
    'admin123',
    'staging123',
    'mock',
    'dummy',
    'placeholder',
    'YOUR_',
    'your-',
    'secret-token',
    'Authorization',
    'password_hash',
    'django.contrib.auth.password_validation',
    'make_password',
    'check_password'
]

findings = []
current_file = "Unknown"

for line in diff_output.splitlines():
    if line.startswith('diff --git'):
        current_file = line.split()[-1].replace('b/', '')
    elif line.startswith('+') and not line.startswith('+++'):
        for pattern, desc in PATTERNS:
            matches = re.finditer(pattern, line)
            for m in matches:
                val = m.group(0)
                if any(safe in val for safe in SAFE_SUBSTRINGS):
                    continue
                if any(safe in line for safe in SAFE_SUBSTRINGS):
                    continue
                trimmed = line.strip()
                if trimmed.startswith('#') or trimmed.startswith('//') or trimmed.startswith('*'):
                    continue
                findings.append((current_file, desc, trimmed[:100]))

print(f"Total findings: {len(findings)}")
for f, desc, sample in findings:
    print(f"  {f} [{desc}]: {sample}")
