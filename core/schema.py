from rest_framework.schemas.openapi import SchemaGenerator


class V1SchemaGenerator(SchemaGenerator):
    """Document only canonical v1 routes, excluding compatibility aliases."""

    def _initialise_endpoints(self):
        super()._initialise_endpoints()
        self.endpoints = [
            endpoint
            for endpoint in self.endpoints
            if endpoint[0].startswith("/api/v1/")
            and endpoint[0] != "/api/v1/schema/"
        ]
