code = r'''
import csv
from competition.models import RankingSnapshot

RANKING_ID = 6
with open("cowrykids.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(
        [
            "S/N",
            "Full Name",
            "Email",
            "Cowrywise Kid username",
        ]
    )
    ranking = RankingSnapshot.objects.prefetch_related(
        "entries__candidate__user",
        "entries__candidate__cowrywise_kid_profile",
    ).get(id=RANKING_ID)

    for idx, entry in enumerate(ranking.entries.all(), 1):
        candidate = entry.candidate
        user = candidate.user
        username = (
            candidate.cowrywise_kid_profile.username
            if hasattr(candidate, 'cowrywise_kid_profile')
            else "N/A"
        )

        writer.writerow(
            [
                idx,
                user.get_full_name(),
                user.email,
                username,
            ]
        )
'''
exec(code)