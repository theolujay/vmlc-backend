import logging
from typing import Optional, Tuple

from django.conf import settings

from identity.models import User, PreRegUser
from vmlc.models import SupportInquiry, FeatureFlag

logger = logging.getLogger(__name__)


def send_system_email(
    subject: str,
    message: str,
    recipient_email: str,
) -> None:
    try:
        from vmlc.tasks import send_mail_task

        send_mail_task.delay(
            subject=subject,
            message=message,
            recipient_list=[recipient_email],
        )
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")


def build_registration_welcome_email(
    user: User,
    generated_password: Optional[str] = None,
) -> Tuple[str, str]:
    login_url = settings.FRONTEND_LOGIN
    password_msg = ""

    if generated_password:
        password_msg = (
            f"Your generated password is: {generated_password}\n"
            "Please use 'Forgot Password' to set your own password.\n\n"
        )

    subject = "Welcome to Verboheit MLC!"

    if hasattr(user, "candidate_profile"):
        message = (
            f"Hi {user.first_name},\n\n"
            "You have successfully registered for the Verboheit Mathematics League Competition.\n\n"
            "We're excited to have you participate and compete with students across regions.\n\n"
            f"{password_msg}"
            f"Login here: {login_url}\n\n"
            "Best regards,\n"
            "The VMLC Team"
        )

    elif hasattr(user, "staff_profile"):
        message = (
            f"Hi {user.first_name},\n\n"
            "Thank you for volunteering to support the Verboheit Mathematics League Competition.\n\n"
            "We appreciate your willingness to contribute to the success of this initiative.\n\n"
            f"{password_msg}"
            f"Login here: {login_url}\n\n"
            "Best regards,\n"
            "The VMLC Team"
        )

    else:
        raise ValueError("User must have either candidate or staff profile")

    return subject, message


def build_pre_registration_email(
    user: PreRegUser,
) -> Tuple[str, str]:
    registration_url = f"{settings.LANDING_BASE_URL}/register"
    interest_type = user.interest_type

    feature_flag_key = (
        "candidate_registration"
        if interest_type == "candidate"
        else "staff_registration"
    )

    if FeatureFlag.get_bool(feature_flag_key, default=False):
        subject = "Registration Is Now Open - Verboheit MLC"
        message = (
            f"Hi {user.full_name},\n\n"
            f"You previously expressed interest in the Verboheit Mathematics League Competition "
            f"as a {interest_type}.\n\n"
            "Registration is now open. You can complete your registration using the link below:\n\n"
            f"{registration_url}\n\n"
            "We look forward to having you on board.\n\n"
            "Best regards,\n"
            "The Verboheit MLC Team"
        )
    else:
        subject = "Your Interest Has Been Recorded - Verboheit MLC"
        message = (
            f"Hi {user.full_name},\n\n"
            f"Thank you for expressing interest in the Verboheit Mathematics League Competition "
            f"as a {interest_type}.\n\n"
            "We'll notify you once registration opens.\n\n"
            f"If you have any questions, contact us at {settings.SUPPORT_EMAIL}.\n\n"
            "Best regards,\n"
            "The Verboheit MLC Team"
        )

    return subject, message


def build_support_confirmation_email(
    inquiry: SupportInquiry,
) -> Tuple[str, str]:
    subject = "Thank You for Supporting Verboheit"

    message = (
        f"Dear {inquiry.full_name},\n\n"
        "Thank you for reaching out to support the Verboheit Mathematics League Competition.\n\n"
        f"We've received your inquiry regarding {inquiry.support_type} support. "
        "A member of our team will review your message and follow up if necessary.\n\n"
        "We truly appreciate your interest in supporting this initiative.\n\n"
        "Best regards,\n"
        "The Verboheit MLC Team"
    )

    return subject, message


def build_support_notification_email(
    inquiry: SupportInquiry,
) -> Tuple[str, str]:
    subject = f"New Support Inquiry: {inquiry.support_type}"

    message = (
        f"A new support inquiry has been received.\n\n"
        f"Name: {inquiry.full_name}\n"
        f"Email: {inquiry.email}\n"
        f"Phone: {inquiry.phone}\n"
        f"Organization: {inquiry.organization}\n"
        f"Support Type: {inquiry.support_type}\n\n"
        f"Message:\n{inquiry.message}\n\n"
        "Please review and follow up."
    )

    return subject, message


def create_email_html(subject, message, otp=None, otp_message=None):
    html_template = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" lang="en">
<head>
<title></title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<!--[if !mso]>-->
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<!--<![endif]-->
<meta name="x-apple-disable-message-reformatting" content="" />
<meta content="target-densitydpi=device-dpi" name="viewport" />
<meta content="true" name="HandheldFriendly" />
<meta content="width=device-width" name="viewport" />
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no, url=no" />
<style type="text/css">
table {
border-collapse: separate;
table-layout: fixed;
mso-table-lspace: 0pt;
mso-table-rspace: 0pt
}
table td {
border-collapse: collapse
}
.ExternalClass {
width: 100%
}
.ExternalClass,
.ExternalClass p,
.ExternalClass span,
.ExternalClass font,
.ExternalClass td,
.ExternalClass div {
line-height: 100%
}
body, a, li, p, h1, h2, h3 {
-ms-text-size-adjust: 100%;
-webkit-text-size-adjust: 100%;
}
html {
-webkit-text-size-adjust: none !important
}
body {
min-width: 100%;
Margin: 0px;
padding: 0px;
}
body, #innerTable {
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale
}
#innerTable img+div {
display: none;
display: none !important
}
img {
Margin: 0;
padding: 0;
-ms-interpolation-mode: bicubic
}
h1, h2, h3, p, a {
line-height: inherit;
overflow-wrap: normal;
white-space: normal;
word-break: break-word
}
a {
text-decoration: none
}
h1, h2, h3, p {
min-width: 100%!important;
width: 100%!important;
max-width: 100%!important;
display: inline-block!important;
border: 0;
padding: 0;
margin: 0
}
a[x-apple-data-detectors] {
color: inherit !important;
text-decoration: none !important;
font-size: inherit !important;
font-family: inherit !important;
font-weight: inherit !important;
line-height: inherit !important
}
u + #body a {
color: inherit;
text-decoration: none;
font-size: inherit;
font-family: inherit;
font-weight: inherit;
line-height: inherit;
}
a[href^="mailto"],
a[href^="tel"],
a[href^="sms"] {
color: inherit;
text-decoration: none
}
</style>
<style type="text/css">
 @media/** (min-width: 481px) {
.hd { display: none!important }
}
</style>
<style type="text/css">
 @media/** (max-width: 480px) {
.hm { display: none!important }
}
</style>
<style type="text/css">
 @media/** (max-width: 480px) {
.t35,.t40{mso-line-height-alt:0px!important;line-height:0!important;display:none!important}.t36{padding:40px!important;border-radius:0!important}.t26{text-align:center!important}.t25{vertical-align:top!important;width:auto!important;max-width:100%!important}
}
</style>
<!--[if !mso]>-->
<link href="https://fonts.googleapis.com/css2?family=Arimo:wght @700&amp;family=Roboto+Mono:wght @600&amp;family=Open+Sans:ital,wght @0,400;0,600;1,400&amp;display=swap" rel="stylesheet" type="text/css" />
<!--<![endif]-->
<!--[if mso]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
</head>
<body id="body" class="t43" style="min-width:100%;Margin:0px;padding:0px;background-color:#FFFFFF;"><div class="t42" style="background-color:#FFFFFF;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" align="center"><tr><td class="t41" style="font-size:0;line-height:0;mso-line-height-rule:exactly;background-color:#FFFFFF;" valign="top" align="center">
<!--[if mso]>
<v:background xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false">
<v:fill color="#FFFFFF"/>
</v:background>
<![endif]-->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" align="center" id="innerTable"><tr><td><div class="t35" style="mso-line-height-rule:exactly;mso-line-height-alt:50px;line-height:50px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t39" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="600" class="t38" style="width:600px;">
<table class="t37" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t36" style="border:1px solid #EBEBEB;overflow:hidden;background-color:#FFFFFF;padding:44px 42px 32px 42px;border-radius:3px 3px 3px 3px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100% !important;"><tr><td align="left">
<table class="t4" role="presentation" cellpadding="0" cellspacing="0" style="Margin-right:auto;"><tr><td width="79" class="t3" style="width:79px;">
<table class="t2" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t1"><div style="font-size:0px;"><img class="t0" style="display:block;border:0;height:auto;width:100%;Margin:0;max-width:100%;" width="79" height="17.643333333333334" alt="" src="https://78cb1dc4-6156-4b00-a1ab-aa0c1ed6c8f8.b-cdn.net/e/629f70ca-d841-4218-8ebc-d3a0670039d8/63418ce1-d325-4122-9886-732d6916f714.png"/></div></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t5" style="mso-line-height-rule:exactly;mso-line-height-alt:10px;line-height:10px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t10" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="514" class="t9" style="width:600px;">
<table class="t8" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t7" style="border-bottom:1px solid #EFF1F4;padding:0 0 12px 0;"><h1 class="t6" style="margin:0;Margin:0;font-family:Arimo,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:20px;font-weight:700;font-style:normal;font-size:20px;text-decoration:none;text-transform:none;letter-spacing:2px;direction:ltr;color:#141414;text-align:left;mso-line-height-rule:exactly;">Your OTP Code</h1></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t11" style="mso-line-height-rule:exactly;mso-line-height-alt:15px;line-height:15px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t16" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="305" class="t15" style="width:305px;">
<table class="t14" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t13" style="padding:20px 0 40px 0;"><p class="t12" style="margin:0;Margin:0;font-family:Roboto Mono,monospace;line-height:25px;font-weight:600;font-style:normal;font-size:40px;text-decoration:none;text-transform:none;letter-spacing:2px;direction:ltr;color:#141414;text-align:center;mso-line-height-rule:exactly;mso-text-raise:-4px;">123456</p></td></tr></table>
</td></tr></table>
</td></tr><tr><td align="center">
<table class="t21" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="514" class="t20" style="width:600px;">
<table class="t19" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t18"><p class="t17" style="margin:0;Margin:0;font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:25px;font-weight:400;font-style:italic;font-size:12px;text-decoration:none;text-transform:none;letter-spacing:-0.1px;direction:ltr;color:#141414;text-align:right;mso-line-height-rule:exactly;mso-text-raise:4px;">...expires in 10 minutes.</p></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t30" style="mso-line-height-rule:exactly;mso-line-height-alt:10px;line-height:10px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t34" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="514" class="t33" style="width:600px;">
<table class="t32" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t31" style="border-top:1px solid #DFE1E4;padding:24px 0 0 0;"><div class="t29" style="width:100%;text-align:center;"><div class="t28" style="display:inline-block;"><table class="t27" role="presentation" cellpadding="0" cellspacing="0" align="center" valign="top">
<tr class="t26"><td></td><td class="t25" valign="top">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="t24" style="width:auto;"><tr><td class="t23" style="background-color:#FFFFFF;text-align:center;line-height:20px;mso-line-height-rule:exactly;mso-text-raise:2px;"><span class="t22" style="display:block;margin:0;Margin:0;font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:20px;font-weight:600;font-style:normal;font-size:14px;text-decoration:none;direction:ltr;color:#222222;text-align:center;mso-line-height-rule:exactly;mso-text-raise:2px;">Verboheit Mathematics League Competition</span></td></tr></table>
</td>
<td></td></tr>
</table></div></div></td></tr></table>
</td></tr></table>
</td></tr></table></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t40" style="mso-line-height-rule:exactly;mso-line-height-alt:50px;line-height:50px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr></table></td></tr></table></div><div class="gmail-fix" style="display: none; white-space: nowrap; font: 15px courier; line-height: 0;">&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;</div></body>
</html>"""

    html_message = html_template.replace("Your OTP Code", subject)

    if otp:
        html_message = html_message.replace("123456", otp)
        if otp_message:
            html_message = html_message.replace(
                "...expires in 10 minutes.", otp_message
            )
    else:
        html_message = html_message.replace(
            '<p class="t12" style="margin:0;Margin:0;font-family:Roboto Mono,monospace;line-height:25px;font-weight:600;font-style:normal;font-size:40px;text-decoration:none;text-transform:none;letter-spacing:2px;direction:ltr;color:#141414;text-align:center;mso-line-height-rule:exactly;mso-text-raise:-4px;">123456</p>',
            f'<p style="font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif; line-height: 25px; font-size: 16px; color: #141414; text-align: left; white-space: pre-wrap; word-break: break-word;">{message}</p>',
        )
        html_message = html_message.replace(
            '<p class="t17" style="margin:0;Margin:0;font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:25px;font-weight:400;font-style:italic;font-size:12px;text-decoration:none;text-transform:none;letter-spacing:-0.1px;direction:ltr;color:#141414;text-align:right;mso-line-height-rule:exactly;mso-text-raise:4px;">...expires in 10 minutes.</p>',
            "",
        )

    return html_message
