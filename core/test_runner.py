"""Keep real throttle behavior without leaking counters or uploads between tests."""
import tempfile
import unittest
from django.core.cache import cache
from django.test import override_settings
from django.test.runner import DiscoverRunner


class IsolatedResult(unittest.TextTestResult):
    def startTest(self, test):
        # SimpleTestCase explicitly forbids database access. Other test classes
        # can safely clear the shared database cache before exercising throttles.
        from django.db import connection
        from django.test import SimpleTestCase
        if not isinstance(test, SimpleTestCase):
            if "hotel_api_cache" in connection.introspection.table_names():
                cache.clear()
        super().startTest(test)


class IsolatedRunner(DiscoverRunner):
    def get_resultclass(self):
        return IsolatedResult

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self.uploads = tempfile.TemporaryDirectory(prefix="hotel-tests-")
        self.upload_settings = override_settings(
            MEDIA_ROOT=self.uploads.name + "/public",
            PRIVATE_MEDIA_ROOT=self.uploads.name + "/private",
        )
        self.upload_settings.enable()

    def teardown_test_environment(self, **kwargs):
        self.upload_settings.disable()
        self.uploads.cleanup()
        super().teardown_test_environment(**kwargs)
