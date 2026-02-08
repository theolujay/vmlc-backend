code = """
from django.core.cache import cache
from django.db import transaction

from identity.models import Candidate, Staff

def normalize_title(name):
    if name:
        return name.lower().title()
    return name

def run():
    print("Starting school name and occupation normalization...")

    with transaction.atomic():
        # Update Candidate school name
        candidates = Candidate.objects.all()
        candidate_count = 0
        for candidate in candidates:
            old_school_name = candidate.school_name
            candidate.school_name = normalize_title(old_school_name)
            if old_school_name != candidate.school_name:
                candidate.save(update_fields=['school_name'])
                candidate_count += 1
        print(f"Updated {candidate_count} Candidate records.")

        # Update Staff occupation
        staff_users = Staff.objects.all()
        staff_count = 0
        for staff in staff_users:
            old_occupation = staff.occupation
            staff.occupation = normalize_title(old_occupation)
            if old_occupation != staff.occupation:
                staff.save(update_fields=['occupation'])
                staff_count += 1
        print(f"Updated {staff_count} Staff records.")

    print("Name normalization complete.")
run()
print("Clearing cache...")
cache.clear()
print("Cache cleared!")
"""
exec(code)
