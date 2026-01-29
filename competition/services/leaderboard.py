import uuid
from typing import Optional, List, Dict
from django.db import transaction
from django.db.models import Sum, Prefetch
from competition.models import (
    Competition, 
    AggregateLeaderboard, 
    AggregateLeaderboardEntry, 
    Stage, 
    Standings, 
    StandingsEntry
)

class LeaderboardService:
    """
    Service to handle retrieval and processing of competition leaderboards.
    """

    @staticmethod
    def get_latest_league_leaderboard(competition: Optional[Competition] = None) -> Optional[AggregateLeaderboard]:
        """
        Retrieves the latest cumulative leaderboard for the league stage.
        
        Args:
            competition: Optional Competition instance. If not provided, 
                        finds the active or latest competition.
        
        Returns:
            AggregateLeaderboard instance with annotated entries, or None.
        """
        if not competition:
            competition = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
            if not competition:
                competition = Competition.objects.order_by('-created_at').first()
        
        if not competition:
            return None

        # Fetch the latest AggregateLeaderboard for LEAGUE stage
        current_leaderboard = AggregateLeaderboard.objects.filter(
            competition=competition,
            stage=Stage.Type.LEAGUE
        ).order_by('-as_of_round').prefetch_related(
            'entries',
            'entries__candidate__user',
            'entries__candidate'
        ).first()

        if not current_leaderboard:
            return None

        # Calculate Rank Change
        LeaderboardService._annotate_rank_changes(current_leaderboard, competition)
        
        return current_leaderboard

    @staticmethod
    def _annotate_rank_changes(leaderboard: AggregateLeaderboard, competition: Competition):
        """
        Calculates and attaches rank_change to each entry in the leaderboard.
        """
        previous_round = (leaderboard.as_of_round or 0) - 1
        previous_ranks = {}
        
        if previous_round > 0:
            previous_leaderboard = AggregateLeaderboard.objects.filter(
                competition=competition,
                stage=Stage.Type.LEAGUE,
                as_of_round=previous_round
            ).prefetch_related('entries').first()
            
            if previous_leaderboard:
                for entry in previous_leaderboard.entries.all():
                    previous_ranks[entry.candidate_id] = entry.overall_rank

        # Attach rank_change to current entries
        entries = list(leaderboard.entries.all())
        for entry in entries:
            prev_rank = previous_ranks.get(entry.candidate_id)
            if prev_rank is not None and entry.overall_rank is not None:
                # Rank change: Positive means improvement (lower rank number)
                entry.rank_change = prev_rank - entry.overall_rank
            else:
                entry.rank_change = 0

        # Sort entries by rank
        entries.sort(key=lambda x: x.overall_rank if x.overall_rank is not None else float('inf'))
        
        # Attach the processed list to the instance for easy access by views/serializers
        leaderboard.processed_entries = entries

    @staticmethod
    @transaction.atomic
    def update_league_leaderboard(competition_id: uuid.UUID, as_of_round: int):
        """
        Aggregates all published league standings up to 'as_of_round' 
        and updates the AggregateLeaderboard.
        """
        competition = Competition.objects.get(id=competition_id)
        
        # 1. Fetch all published league standings up to as_of_round
        published_standings = Standings.objects.filter(
            competition=competition,
            stage=Stage.Type.LEAGUE,
            round__lte=as_of_round,
            is_published=True
        ).values_list('id', flat=True)

        if not published_standings:
            return None

        # 2. Aggregate scores by candidate
        candidate_totals = StandingsEntry.objects.filter(
            standings_id__in=published_standings
        ).values('candidate_id', 'candidate_competition_id').annotate(
            total_score=Sum('exam_score')
        ).order_by('-total_score')

        if not candidate_totals:
            return None

        # 3. Create or update AggregateLeaderboard for this round
        leaderboard, _ = AggregateLeaderboard.objects.get_or_create(
            competition=competition,
            stage=Stage.Type.LEAGUE,
            as_of_round=as_of_round
        )

        # 4. Prepare and bulk create entries
        # Calculate ranks (dense rank)
        entries_to_create = []
        previous_score = None
        current_rank = 0
        
        for idx, item in enumerate(candidate_totals):
            score = item['total_score']
            if score != previous_score:
                current_rank = idx + 1
            
            entries_to_create.append(
                AggregateLeaderboardEntry(
                    leaderboard=leaderboard,
                    candidate_id=item['candidate_id'],
                    candidate_competition_id=item['candidate_competition_id'],
                    total_score=score,
                    overall_rank=current_rank
                )
            )
            previous_score = score

        # Clear existing entries for this leaderboard if any
        leaderboard.entries.all().delete()
        AggregateLeaderboardEntry.objects.bulk_create(entries_to_create)

        return leaderboard
