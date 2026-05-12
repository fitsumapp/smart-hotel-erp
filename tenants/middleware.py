"""
tenants/middleware.py
— Cross-Tenant Security Middleware.

Ensures:
  1. Hotel staff can ONLY access the tenant (subdomain) they belong to.
  2. Superusers / platform admins can access any tenant.
  3. Anonymous requests pass through (login endpoints, public payment pages).
"""
from django.db import models, connection
from django.http import JsonResponse
from tenants.models import Hotel


class TenantUserIsolationMiddleware:
    """
    Runs AFTER TenantMainMiddleware (which sets connection.tenant).
    Checks that the authenticated user is allowed on the current tenant schema.
    """

    EXEMPT_PATH_PREFIXES = (
        "/admin/",
        "/api/users/login/",
        "/api/users/register/",
        "/api/users/verify-otp/",
        "/api/users/payments/public/",
        "/api/users/payments/chapa/webhook/",
        "/api/users/public-booking/",
        "/api/users/reservations/public/",
        "/api/users/reservations/qr-checkin/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip unauthenticated requests (login, public payment pages, etc.)
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return self.get_response(request)

        # Skip exempt paths
        path = request.path_info
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        # Platform admins can access any schema
        user = request.user
        if user.is_superuser or getattr(user, "is_platform_admin", False):
            return self.get_response(request)

        # Get the current tenant from the DB connection
        try:
            from django.db import connection
            current_schema = connection.schema_name
        except Exception:
            return self.get_response(request)

        # Allow public schema access freely
        if current_schema == "public":
            return self.get_response(request)

        # Enforce tenant match: user must belong to this tenant schema
        user_schema = getattr(user, "tenant_schema", None)
        if user_schema and user_schema != current_schema:
            return JsonResponse(
                {
                    "error": "Access denied.",
                    "detail": (
                        f"Your account does not have access to this hotel. "
                        f"Please log in at your hotel's subdomain."
                    ),
                },
                status=403,
            )

        return self.get_response(request)


class LocalhostTenantRoutingMiddleware:
    """
    Allows localhost public-booking requests to target a specific tenant schema
    using X-Tenant-Schema header or ?tenant=... query string.
    """

    TENANT_HINT_PATH_PREFIXES = (
        "/api/users/public-booking/",
        "/api/users/reservations/public/",
        "/api/users/reservations/qr-checkin/",
        "/api/users/payments/chapa/webhook/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info or ""
        host = request.get_host().split(":")[0]
        
        # If we are on public schema and on localhost/127.0.0.1, 
        # allow manual tenant routing via headers/params for ALL API paths.
        if (
            connection.schema_name == "public"
            and host in {"localhost", "127.0.0.1"}
            and path.startswith("/api/")
        ):
            tenant_schema = (
                request.headers.get("X-Tenant-Schema")
                or request.GET.get("tenant")
                or request.POST.get("tenant")
            )
            if tenant_schema:
                # 1. Try direct schema name match
                tenant = Hotel.objects.filter(schema_name=tenant_schema, is_active=True).first()
                
                # 2. Try with hotel_ prefix
                if not tenant and not tenant_schema.startswith('hotel_'):
                    tenant = Hotel.objects.filter(schema_name=f"hotel_{tenant_schema}", is_active=True).first()
                
                # 3. Try matching via Domain (most reliable for local development)
                if not tenant:
                    from tenants.models import Domain
                    # Look for domain like 'barok.localhost'
                    domain_obj = Domain.objects.filter(
                        models.Q(domain=f"{tenant_schema}.localhost") |
                        models.Q(domain=tenant_schema)
                    ).select_related('tenant').first()
                    if domain_obj:
                        tenant = domain_obj.tenant

                if tenant:
                    connection.set_tenant(tenant)
        return self.get_response(request)
