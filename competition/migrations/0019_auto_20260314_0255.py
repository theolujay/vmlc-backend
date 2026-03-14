from django.db import migrations

def make_proctoring_status_null_for_absentees(apps, schema_editor):
    RankingSnapshotEntry = apps.get_model("competition", "RankingSnapshotEntry")
    # Candidates with no exam_score (absent) should have null proctoring_status
    RankingSnapshotEntry.objects.filter(exam_score=None).update(proctoring_status=None)

class Migration(migrations.Migration):

    dependencies = [
        ("competition", "0018_alter_rankingsnapshotentry_proctoring_status"),
    ]

    operations = [
        migrations.RunPython(make_proctoring_status_null_for_absentees),
    ]
