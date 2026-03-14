from django.db import migrations
from django.db.models import Count

def make_proctoring_status_null_for_absentees(apps, schema_editor):
    ExamAccess = apps.get_model("vmlc", "ExamAccess")
    # Candidates with no heartbeats and not manually reviewed should have null proctoring_status
    ExamAccess.objects.annotate(hb_count=Count("heartbeats")).filter(
        hb_count=0, 
        is_manually_reviewed=False
    ).update(proctoring_status=None)

class Migration(migrations.Migration):

    dependencies = [
        ("vmlc", "0058_alter_examaccess_proctoring_status"),
    ]

    operations = [
        migrations.RunPython(make_proctoring_status_null_for_absentees),
    ]
