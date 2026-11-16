import urllib.request, json, time, sys, os
sys.path.insert(0, os.path.abspath("."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from apps.identity.services import get_tokens_for_user
from hotel.models import StockLocation, InventoryCategory, InventoryItem, StocktakeSession

User = get_user_model()
admin = User.objects.filter(role='admin', is_active=True).first()
counter = User.objects.filter(role='inventory', is_active=True).first()
if not counter:
    counter = User.objects.create_user(username="test_counter_live", password="password123", role="inventory", is_active=True)

admin_jwt = get_tokens_for_user(admin)['access']
counter_jwt = get_tokens_for_user(counter)['access']

loc = StockLocation.objects.first()
cat = InventoryCategory.objects.first()

def make_req(url, method='GET', data=None, token=admin_jwt):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, err_body

print('1. Creating draft session via live API...')
status, session_data = make_req('http://127.0.0.1:8000/api/v1/stocktaking/sessions/', 'POST', {
    'location': loc.id,
    'category': cat.id,
    'counting_mode': 'blind',
    'title': f'Live HTTP Verification Session {int(time.time())}'
})
print(f"   Created Session #{session_data.get('session_number')} (ID {session_data.get('id')}) - Status: {status}")
sess_id = session_data['id']
item_id = session_data['items'][0]['item']

print('2. Submitting physical count via /record-counts/ as counter...')
counts_payload = [{'item_id': it['item'], 'counted_quantity': 10.0} for it in session_data['items']]
status, res = make_req(f'http://127.0.0.1:8000/api/v1/stocktaking/sessions/{sess_id}/record-counts/', 'POST', {
    'counts': counts_payload
}, token=counter_jwt)
print(f"   Record counts HTTP status: {status}, new session status: {res.get('status')}")
assert status == 200
assert res['status'] == 'under_review'

print('3. Counter attempting SoD self-approval via /approve/...')
status, res = make_req(f'http://127.0.0.1:8000/api/v1/stocktaking/sessions/{sess_id}/approve/', 'POST', {
    'notes': 'Self approval attempt'
}, token=counter_jwt)
print(f"   Counter self-approval HTTP status: {status} (Expected 403 Forbidden)")
assert status == 403

print('4. Supervisor requesting recount via /request-recount/...')
stk_item_id = session_data['items'][0]['id']
status, res = make_req(f'http://127.0.0.1:8000/api/v1/stocktaking/sessions/{sess_id}/request-recount/', 'POST', {
    'item_ids': [stk_item_id],
    'reason': 'Recount variance check'
}, token=admin_jwt)
print(f"   Request recount HTTP status: {status}, new status: {res.get('status')}")
assert status == 200
assert res['status'] == 'recount_required'

print('5. Counter submitting recount via /submit-recount/...')
status, res = make_req(f'http://127.0.0.1:8000/api/v1/stocktaking/sessions/{sess_id}/submit-recount/', 'POST', {
    'recounts': [{'id': stk_item_id, 'recounted_quantity': 10.0, 'notes': 'Recount confirmed'}]
}, token=counter_jwt)
print(f"   Submit recount HTTP status: {status}, new status: {res.get('status')}")
assert status == 200
assert res['status'] == 'under_review'

print('6. Admin approving session via /approve/...')
status, res = make_req(f'http://127.0.0.1:8000/api/v1/stocktaking/sessions/{sess_id}/approve/', 'POST', {
    'notes': 'Final approval by admin'
}, token=admin_jwt)
print(f"   Approval HTTP status: {status}, response: {res}")
assert status == 200
assert res['status'] == 'approved'

print('7. Attempting DELETE on approved session via /sessions/{id}/...')
status, res = make_req(f'http://127.0.0.1:8000/api/v1/stocktaking/sessions/{sess_id}/', 'DELETE', token=admin_jwt)
print(f"   DELETE approved session HTTP status: {status} (Expected 400 Bad Request)")
assert status == 400

print('8. Creating second session to test /cancel/ endpoint...')
status, s2 = make_req('http://127.0.0.1:8000/api/v1/stocktaking/sessions/', 'POST', {
    'location': loc.id,
    'counting_mode': 'blind',
    'title': 'Cancellation Test Session'
})
s2_id = s2['id']
status, res = make_req(f'http://127.0.0.1:8000/api/v1/stocktaking/sessions/{s2_id}/cancel/', 'POST', {
    'reason': 'Aborted for test'
}, token=admin_jwt)
print(f"   Cancel session HTTP status: {status}, status: {res.get('status')}")
assert status == 200
assert res['status'] == 'cancelled'

print('\n======================================================================')
print('ALL LIVE HTTP ENDPOINT VERIFICATIONS PASSED 100%!')
print('======================================================================')
