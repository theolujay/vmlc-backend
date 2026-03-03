code = r'''
import logging
from identity.models import Candidate
from comms.services.email import send_system_email

logger = logging.getLogger(__name__)

EMAIL_LIST = [
    "adebayovictor3433@gmail.com",
    "fasugba2000@gmail.com",
    "patajie1984@gmail.com",
    "nnannaihechi60@gmail.com",
    "ukpeborlucky@yahoo.com",
    "obiohaukachidavid@gmail.com",
    "rasaqabiodunyusuff@gmail.com",
    "paschaljompe@gmail.com",
    "isabellaubendu@gmail.com",
    "alexisoscar565@gmail.com",
    "jaobagade@gmail.com",
    "adebolaobj@gmail.com",
    "scountain@gmail.com",
    "anjolaoluwalawal1@gmail.com",
    "andrewngaju63@gmail.com",
    "olujay.mail@gmail.com",
]

candidates = Candidate.objects.filter(
    user__email__in=EMAIL_LIST
).select_related("user")

subject = "Your Account Has Been Reactivated"

message_template = """
Dear {candidate_fullname},

Your account was deactivated in error earlier today. We apologize for this and confirm that the issue has now been resolved. Your account has been fully restored.

You can log in and continue using the portal as usual. Please let us know if you experience any further issues.

Regards,
VMLC Team
"""

print(f"Attempting to send emails to {candidates.count()} candidates...")

sent_count = 0
failed_count = 0

for candidate in candidates:
    full_name = candidate.user.get_full_name() or candidate.user.email
    message = message_template.format(candidate_fullname=full_name)

    try:
        send_system_email(
            subject=subject,
            message=message,
            recipient_email=candidate.user.email,
        )
        print(f"Successfully sent email to {candidate.user.email}")
        sent_count += 1
    except Exception as e:
        logger.error(f"Failed to send email to {candidate.user.email}: {e}")
        print(f"Failed to send email to {candidate.user.email}. Check logs for details.")
        failed_count += 1

print(f"\nFinished sending emails.")
print(f"Total candidates processed: {candidates.count()}")
print(f"Emails successfully sent: {sent_count}")
print(f"Emails failed to send: {failed_count}")
'''
exec(code)

code2 = r"""
from vmlc.models import CandidateExamResult, CandidateAnswer, Question

answer_count, _ = CandidateAnswer.objects.filter(
    candidate_exam_result__isnull=True
).delete()

# purge archived questions with no relation to any candidate answer
purged_count, _ = Question.objects.filter(
    candidateanswer__isnull=True,
    is_archived=True
).delete()

print(f"Purged {answer_count} orphaned candidate answers and purged {purged_count} archived questions with no related candidate answer")
"""
exec(code2)


from competition.models import RankingSnapshot

ranking = RankingSnapshot.objects.filter(is_active=True).update(is_active=False)
