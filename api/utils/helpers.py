"""
Utility function to serialize candidate details along with score summaries.
"""

from django.utils import timezone


from ..models import CandidateScore, CandidateAnswer
from ..serializers import CandidateDetailSerializer


def get_candidate_with_scores(candidate):
    """
    Returns serialized candidate data including their exam scores, total score,
    and average score.

    Optimized to use `candidate.total_score` if it has been annotated.
    Falls back to manual calculation if not annotated.

    Args:
        candidate (Candidate): The candidate instance.

    Returns:
        dict: Serialized candidate data with appended scores, total_score, and average_score.
    """
    if hasattr(candidate, "total_score"):
        total = float(getattr(candidate, "total_score", 0) or 0)
        count = candidate.scores.count()
        avg = total / count if count else 0.0
    else:
        # Fallback to Python calculation
        scores = list(candidate.scores.all())
        total = sum(float(s.score) for s in scores)
        avg = total / len(scores) if scores else 0.0

    serializer = CandidateDetailSerializer(candidate)
    data = serializer.data
    data.update(
        {
            "scores": [
                {
                    "exam_id": s.exam.id,
                    "exam_title": s.exam.title,
                    "score": float(s.score),
                    "date_recorded": s.date_recorded,
                    "last_updated": s.date_updated,
                    "submitted_by": (
                        {
                            "id": s.submitted_by.user.id,
                            "name": s.submitted_by.user.get_full_name(),
                        }
                        if s.submitted_by
                        else None
                    ),
                }
                for s in candidate.scores.all().select_related("exam", "submitted_by")
            ],
            "total_score": total,
            "average_score": avg,
        }
    )
    return data


def auto_score(candidate_score):
    """
    Scores a candidate's exam based on their submitted answers.
    """
    answers = CandidateAnswer.objects.filter(candidate_score=candidate_score)
    total_questions = candidate_score.exam.questions.count()
    print(f"Scoring CandidateScore: {candidate_score.pk}")
    print(f"Total Answers Submitted: {answers.count()}")
    print(f"Total Questions in Exam: {total_questions}")

    correct_count = sum(
        1
        for answer in answers
        if answer.selected_option == answer.question.correct_answer
    )
    print(f"Correct Answers: {correct_count}")

    score = (correct_count / total_questions) * 100 if total_questions else 0
    print(f"Final Score: {score}")

    candidate_score.score = round(score, 2)
    candidate_score.date_recorded = timezone.now()
    candidate_score.auto_score = True
    candidate_score.save()
