# Questions API Specification (V2)

This document outlines the V2 API endpoints for question management. V1 endpoints are considered deprecated and should be migrated to V2.

## Base URLs
- **V2 (Current):** `/v2/`
- **V1 (Deprecated):** `/v1/`

---

## 1. List Questions
**Endpoint:** `GET /v2/questions/`  
**Description:** Returns a paginated and filtered list of all non-archived questions. Includes real-time question pool statistics.  
**Permissions:** `moderator`

### Response Body
```json
{
  "count": 100,
  "next": "...",
  "previous": null,
  "question_pool_data": {
    "total_questions": 500,
    "hard_questions_count": 100,
    "moderate_questions_count": 250,
    "easy_questions_count": 150
  },
  "results": [
    {
      "id": 1,
      "text": "What is 2+2?",
      "option_a": "3",
      "option_b": "4",
      "option_c": "5",
      "option_d": "6",
      "correct_answer": "B",
      "difficulty": "easy",
      "exam_ids": ["uuid-exam-1", "uuid-exam-2"],
      "related_exams_count": 2,
      "created_at": "2026-02-02T12:00:00Z",
      "created_by": { "id": "uuid", "full_name": "Staff Name" },
      "updated_at": "...",
      "updated_by": { "id": "uuid", "full_name": "Staff Name" }
    }
  ]
}
```

---

## 2. Create Question
**Endpoint:** `POST /v2/questions/`  
**Description:** Creates a new question. Optionally assigns the question to one or more exams.  
**Permissions:** `ActiveModeratorPermissions`

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `text` | String | **Required.** The question text. |
| `option_a` | String | **Required.** |
| `option_b` | String | **Required.** |
| `option_c` | String | **Required.** |
| `option_d` | String | **Required.** |
| `correct_answer` | String | **Required.** (A, B, C, or D). |
| `difficulty` | String | Choices: `easy`, `moderate`, `hard`. |
| `exam_ids` | Array[UUID] | Optional. List of exam IDs to assign the question to. **Constraint:** Exams must be in `draft` or `scheduled` status. |

---

## 3. Get Question Details
**Endpoint:** `GET /v2/questions/{question_id}/`  
**Description:** Retrieves detailed information about a question, including full metadata for all associated exams across competitions.  
**Permissions:** `ActiveModeratorPermissions`

### Response Body
```json
{
  "id": 1,
  "text": "...",
  "related_exams": [
    {
      "id": "uuid",
      "title": "League Round 1",
      "competition_title": "Verboheit MLC 1.0",
      "stage": "league",
      "round": 1,
      "scheduled_date": "...",
      "status": "concluded"
    }
  ],
  "related_exams_count": 1,
  "created_by": { ... },
  "updated_by": { ... }
}
```

---

## 4. Bulk Actions (Unified)
**Endpoint:** `POST /v2/questions/bulk-action/`  
**Description:** Perform batch operations on multiple questions.  
**Permissions:** `ActiveAdminPermissions`

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `action` | String | **Required.** `archive`, `assign`, or `unassign`. |
| `question_ids` | Array[Int] | **Required.** List of question IDs. |
| `exam_ids` | Array[UUID] | **Required for assign/unassign.** Target exams. **Constraint:** For `assign`/`unassign`, exams must be in `draft` or `scheduled` status. |

#### Example: Assign Questions to Exams
```json
{
    "action": "assign",
    "question_ids": [1, 2, 3],
    "exam_ids": ["uuid-exam-1"]
}
```

---

## 5. List Exam Questions
**Endpoint:** `GET /v2/exams/{exam_id}/questions/`  
**Description:** Returns all questions belonging to a specific exam. Useful for exam previews.  
**Permissions:** `ActiveAdminPermissions`

---

## 6. Update/Delete Question
- **Update:** `PUT/PATCH /v2/questions/{question_id}/`
- **Archive:** `DELETE /v2/questions/{question_id}/` (Safe delete via archiving)