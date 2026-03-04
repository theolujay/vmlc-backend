# Ranking Snapshot API

This endpoint retrieves the official ranking for a specific exam within the competition. It includes all candidates' scores and ranks for that exam.

## Endpoint

**Path:** `/competition/rankings/<uuid:exam_id>/`
**Method:** `GET`
**Authentication:** Required (Candidates in the competition or Staff)

## Caching

The response is cached for 24 hours. The cache is automatically invalidated when a ranking is regenerated or the underlying exam is updated.

## Response Structure

The response is a JSON object representing a `RankingSnapshot`.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer | Unique identifier for the ranking snapshot record. |
| `competition` | Integer | ID of the competition edition. |
| `stage` | String | Competition stage code (`screening`, `league`, `final`). |
| `stage_display` | String | Human-readable stage name (e.g., "Screening", "League"). |
| `round` | Integer \| null | Round number within the stage (relevant for League). |
| `exam` | UUID | Unique identifier of the source exam. |
| `facilitator_system`| String | The system that delivered the exam (`vmlc`, `esturdi`). |
| `is_published` | Boolean | Whether this ranking is currently visible to candidates. |
| `published_at` | DateTime \| null| When the ranking was officially published. |
| `meta` | Object | Auxiliary metadata (e.g. `ranking_policy`, `tie_break_strategy`, `generated_by`). `ranking_policy` defaults to `standard`. `tie_break_strategy` usually defaults to `submission_time_asc`. |
| `created_at` | DateTime | When the snapshot was generated. |
| `entries` | Array | List of individual candidate ranking entries. |

### `entries` Array Item:
Represents a single candidate's performance and rank in this snapshot.

| Field | Type | Description |
| :--- | :--- | :--- |
| `candidate` | UUID | Unique identifier for the candidate. |
| `candidate_info` | Object | Nested object containing candidate's profile details. |
| `exam_score` | Float \| "absent"| The candidate's final score for this exam. Returns `"absent"` for absentees. |
| `rank` | Integer | The rank assigned to the candidate. |
| `percentile` | Float \| null | Computed percentile score (0-100). |
| `time_used` | Integer \| null | Time taken to complete the exam in seconds. |
<!-- | `tie_break_reason` | String \| null | Explanation for why a specific rank was assigned (e.g., tie-break details). | -->

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
    "id": 12,
    "competition": 1,
    "stage": "league",
    "stage_display": "League",
    "round": 1,
    "exam": "550e8400-e29b-41d4-a716-446655440000",
    "facilitator_system": "vmlc",
    "is_published": true,
    "published_at": "2026-03-01T12:00:00Z",
    "meta": {
        "generated_by": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "ranking_policy": "standard",
        "tie_break_strategy": "submission_time_asc"
    },
    "created_at": "2026-03-01T11:45:00Z",
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
            "exam_score": 95.0,
            "rank": 1,
            "percentile": 100.0
        },
        {
            "candidate": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
            "candidate_info": {
                "id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
                "full_name": "Bob Builder",
                "email": "bob@example.com",
                "state": "Kano",
                "school_name": "Construction Academy",
                "school_type": "public",
                "current_class": "SS2"
            },
            "exam_score": "absent",
            "rank": 115,
            "percentile": 4.5
        }
    ]
}
```
