code = """
from django.core.mail import send_mass_mail
from vmlc.models import FeatureFlag
from identity.models import PreRegUser


def send_email_reminder():
    # Try to get the expiry date from FeatureFlag
    try:
        flag = FeatureFlag.objects.get(key="candidate_registration")
        # Use auto_off_date as the source for expiry time
        expiry_date = getattr(flag, 'expiry_date', flag.auto_off_date)
    except FeatureFlag.DoesNotExist:
        print("Error: FeatureFlag 'candidate_registration' not found.")
        return
    
    if not expiry_date:
        print("Error: No expiry date found on 'candidate_registration' feature flag.")
        return
    
    # Filter for pre-registered candidates
    candidates = PreRegUser.objects.filter(
        interest_type=PreRegUser.InterestType.CANDIDATE
    )
    
    if not candidates.exists():
        print("No pre-registered candidates found.")
        return
    
    emails = list(candidates.values_list('email', flat=True))
    emails = [email for email in emails if email]
    
    if not emails:
        print("No valid emails found for candidates.")
        return
    
    # Format the expiry date for the email
    formatted_expiry = expiry_date.strftime("%A, %B %d, %Y at %I:%M %p")
    
    subject = "Registration Closes in 24 hours - Verboheit Math Competition 3.0"
    message = (
        "Hello,\\n\\n"
        "This is a quick reminder that registration for Verboheit Mathematics League Competition (VMLC 3.0) "
        f"closes on {formatted_expiry}.\\n\\n"
        "We understand that you couldn't register last time we saw you, but this is your final window "
        "to secure a spot in the competition.\\n\\n"
        "Please complete your registration now:\\n"
        "https://verboheit.org/register\\n\\n"
        "We look forward to having you compete.\\n\\n"
        "Regards,\\n"
        "The VMLC Team"
    )
    
    from_email = "Verboheit MLC <verboheitvmlc@gmail.com>"
    
    print(f"Preparing to send reminder to {len(emails)} candidates...")
    
    try:
        sent_count = 0
        for email in emails:
            send_mass_mail(
                ((subject, message, from_email, [email]),),
                fail_silently=False
            )
            sent_count += 1
        print(f"Successfully sent email reminders to {sent_count} candidates.")
    except Exception as e:
        print(f"An error occurred while sending emails: {e}")


send_email_reminder()
"""
exec(code)
