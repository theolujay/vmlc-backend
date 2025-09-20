from django.test import TestCase
from vmlc.utils.auth import generate_secure_numeric_otp

class AuthUtilsTest(TestCase):

    def test_generate_secure_numeric_otp(self):
        otp = generate_secure_numeric_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())
