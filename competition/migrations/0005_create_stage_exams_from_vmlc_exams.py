# Written by Olujay on 2026-01-28 16:24

from django.db import migrations, models
import django.db.models.deletion


def create_stage_exams_from_vmlc_exams(apps, schema_editor):
    """
    Create StageExam records for vmlc.Exam rows that contain stage/round-like metadata.

    Behavior:
    - If there is no Competition row, does nothing (safe on empty production).
    - For each vmlc.Exam that has a non-empty 'stage' or 'level'/'round' attribute,
      attempt to find a Stage under the first Competition that matches that type.
    - If the Stage is missing, create it under the first Competition (order=0, empty description).
    - Create a StageExam linking the Stage and the vmlc.Exam. If a mapping already exists, skip.
    """
    Exam = apps.get_model("vmlc", "Exam")
    Competition = apps.get_model("competition", "Competition")
    Stage = apps.get_model("competition", "Stage")
    StageExam = apps.get_model("competition", "StageExam")

    competitions = list(Competition.objects.all())
    if not competitions:
        # Nothing to attach to - skip, since there is no competition yet
        return

    default_competition = competitions[0]

    # helper to read possible fields from vmlc.Exam (backwards compatible)
    def get_exam_stage_and_round(exam_obj):
        # exam may have 'stage', 'level', 'round', 'round_number' variants from different versions
        stage = getattr(exam_obj, "stage", None)
        round_val = getattr(exam_obj, "round", None)
        if round_val is None:
            round_val = getattr(exam_obj, "level", None)
        # normalize types
        if isinstance(round_val, (str,)):
            try:
                round_val = int(round_val)
            except Exception:
                round_val = None
        return stage, round_val

    # iterate exams
    for exam in Exam.objects.all():
        stage_val, round_val = get_exam_stage_and_round(exam)
        if not stage_val:
            # nothing to migrate for this exam
            continue

        # try to find an existing Stage under default_competition
        stage_obj = Stage.objects.filter(
            competition=default_competition, type=stage_val
        ).first()
        if not stage_obj:
            # create a minimal Stage so StageExam can reference it
            stage_obj = Stage.objects.create(
                competition=default_competition,
                type=stage_val,
                order=0,
                description=f"Auto-created stage from migration for type={stage_val}",
            )

        # ensure we don't duplicate
        exists = StageExam.objects.filter(
            competition_stage=stage_obj, vmlc_exam_id=exam.pk
        ).exists()
        if exists:
            continue

        StageExam.objects.create(
            competition_stage=stage_obj,
            exam=exam,
            round=round_val,
            is_active=True,
            config={},
        )


def reverse_create_stage_exams(apps, schema_editor):
    StageExam = apps.get_model("competition", "StageExam")
    # Remove StageExam records that were created without an explicit marker.
    # This will delete StageExam rows for which config is blank and is_active=True
    StageExam.objects.filter(is_active=True, config={}).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("competition", "0004_stageexam"),  # update as appropriate
        (
            "vmlc",
            "0039_remove_candidate_created_by_remove_candidate_user_and_more",
        ),  # adjust to your vmlc migrations
    ]

    operations = [
        migrations.RunPython(
            create_stage_exams_from_vmlc_exams, reverse_create_stage_exams
        ),
    ]
