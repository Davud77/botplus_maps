import unittest
from scripts.collect_service_logs import redact
class LogRedactionTests(unittest.TestCase):
    def test_credentials_and_tokens_are_not_exported(self):
        value=redact('dsn=postgresql://botplus:sensitive-value@db/test password=another-secret token=private-token eyJabc.abcdef.123456')
        for secret in ['sensitive-value','another-secret','private-token','eyJabc.abcdef.123456']:self.assertNotIn(secret,value)
        self.assertIn('[redacted',value)
