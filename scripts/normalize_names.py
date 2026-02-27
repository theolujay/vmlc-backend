code = r"""
from django.core.cache import cache
from django.db import transaction

from identity.models import User

def normalize_email(email):
    if email:
        return email.lower()
    return email

def run():
    print("Starting user email normalization...")

    user_count = 0
    with transaction.atomic():
        # Update email addresses
        users = User.objects.all()
        for user in users:
            old_email = user.email
            user.email = normalize_email(old_email)
            if old_email != user.email:
                user.save(update_fields=['email'])
                user_count += 1

    print(f"Email normalization complete for {user_count} users")
run()
print("Clearing cache...")
cache.clear()
print("Cache cleared!")
"""
exec(code)

code2 = r"""
from django.db.models import Func, F, Value
from django.db.models.functions import Lower
from identity.models import User
from collections import defaultdict

groups = defaultdict(list)
for user in User.objects.all():
    groups[user.email.lower()].append(user)

conflicts = {email: users for email, users in groups.items() if len(users) > 1}
for email, users in conflicts.items():
    print(email, [u.pk for u in users])
"""
exec(code2)


code3 = r"""
from uuid import UUID

from identity.models import User

conflict_pairs = [
    [UUID('39c67827-5572-457c-9825-edce8e86dcdf'), UUID('3a88d3ac-6d71-48ae-a036-0d62a924a119')],
    [UUID('0bc90812-64a0-4a4f-923f-f1edf86c535a'), UUID('9ed769a7-5bb7-4571-930c-f847964fdbd0')],
]

for pair in conflict_pairs:
    print("---")
    for pk in pair:
        u = User.objects.get(pk=pk)
        print(f"  pk={u.pk} email={u.email!r} date_joined={u.date_joined} last_login={u.last_login} is_active={u.is_active}")
"""
exec(code3)