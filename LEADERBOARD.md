# League Leaderboard API

This endpoint provides the cumulative standings for all candidates in the League stage of the competition. It aggregates performance across all concluded rounds within the stage.

## Endpoint

**Path:** `/competition/leaderboard/league/`  
**Method:** `GET`  
**Authentication:** Required (Candidates in the league or Staff)

## Response Structure

The response is a JSON object representing a `LeagueLeaderboard`.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer | Unique identifier for the leaderboard record. |
| `competition` | Integer | ID of the competition edition. |
| `stage` | String | Competition stage code (`league`). |
| `stage_display` | String | Human-readable stage name (e.g., "League"). |
| `as_of_round` | Integer \| null | The most recent round included in this aggregate leaderboard. |
| `created_at` | DateTime | When the leaderboard was first generated. |
| `updated_at` | DateTime | When the leaderboard was last refreshed. |
| `entries` | Array | List of aggregated candidate performance records. |

### `entries` Array Item:
Represents a single candidate's cumulative performance in the league stage.

| Field | Type | Description |
| :--- | :--- | :--- |
| `candidate` | UUID | Unique identifier for the candidate. |
| `candidate_info` | Object | Nested object containing candidate's profile details. |
| `total_score` | Float | The sum of all scores across published rounds. |
| `overall_rank` | Integer | The dense rank based on `total_score`. |
| `rank_change` | Integer | The change in rank compared to the previous round. Positive is an improvement, negative is a drop. |

#### `candidate_info` Nested Object:
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Unique identifier for the candidate. |
| `full_name` | String | Full name of the candidate. |
| `email` | String | Candidate's email address. |
| `state` | String | State of origin or residence. |
| `school_name` | String | Name of the candidate's school. |
| `school_type` | String | Category of school (`public`, `private`). |
| `current_class` | String | Current class level (e.g., `SS1`, `SS2`, `SS3`). |

---

## Example Response

```json
{
    "id": 5,
    "competition": 1,
    "stage": "league",
    "stage_display": "League",
    "as_of_round": 3,
    "created_at": "2026-03-01T15:00:00Z",
    "updated_at": "2026-03-01T15:30:00Z",
    "entries": [
        {
            "candidate": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "candidate_info": {
                "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
                "full_name": "Alice Wonderland",
                "email": "alice@example.com",
                "state": "Oyo",
                "school_name": "Wonderland High",
                "school_type": "private",
                "current_class": "SS3"
            },
            "total_score": 285.5,
            "overall_rank": 1,
            "rank_change": 0
        },
        {
            "candidate": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33",
            "candidate_info": {
                "id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33",
                "full_name": "Charlie Bucket",
                "email": "charlie@example.com",
                "state": "Abia",
                "school_name": "Golden High",
                "school_type": "private",
                "current_class": "SS3"
            },
            "total_score": 270.0,
            "overall_rank": 2,
            "rank_change": 2
        }
    ]
}
```
