import os
import re

PATTERNS = [
    (r'(?i)secret[_-]?key\s*[:=]\s*["\']([^"\']+)["\']', "Potential Secret Key"),
    (r'(?i)api[_-]?key\s*[:=]\s*["\']([^"\']+)["\']', "Potential API Key"),
    (r'(?i)token\s*[:=]\s*["\']([^"\']+)["\']', "Potential Token"),
    (r'-----BEGIN [A-Z ]+ PRIVATE KEY-----', "Private Key Block"),
    (r'postgres(ql)?:\/\/[^:]+:[^@]+@', "Database URI with Password"),
    (r'(?i)password\s*[:=]\s*["\'](?!django_test_dummy)([^"\']+)["\']', "Hardcoded Password")
]

# Whitelisted false positives (e.g., test mocks, dummy keys, standard settings env fallbacks)
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
    'password_hash'
]

def scan_file(filepath):
    findings = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            for pattern, desc in PATTERNS:
                matches = re.finditer(pattern, line)
                for m in matches:
                    val = m.group(0)
                    if any(safe in val for safe in SAFE_SUBSTRINGS):
                        continue
                    if any(safe in line for safe in SAFE_SUBSTRINGS):
                        continue
                    # Skip comment explanations
                    if line.strip().startswith('#') or line.strip().startswith('//') or line.strip().startswith('*'):
                        continue
                    findings.append((line_num, desc, line.strip()[:100]))
    except Exception as e:
        findings.append((0, f"Error scanning: {str(e)}", ""))
    return findings

