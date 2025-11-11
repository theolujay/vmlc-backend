from django.test import TestCase
from vmlc.utils.auth import generate_otp


class AuthUtilsTest(TestCase):

    def test_generate_otp(self):
        otp = generate_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())
