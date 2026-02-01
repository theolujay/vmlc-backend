# Questions API Specification

This document outlines the API endpoints related to questions management.

## Base URLs
- V1: `/v1/`
- V2: `/v2/`

---

## 1. List Questions
**Endpoint:** `GET /v1/questions/`  
**Description:** Returns a paginated and filtered list of all non-archived questions.  
**Permissions:** `ActiveModeratorPermissions` (Moderator, Admin, or Superadmin)

### Response Body
```json
{
  "count": 100,
  "next": "http://api.vmlc.com/v1/questions/?page=2",
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
      "text": "What is the capital of France?",
      "option_a": "London",
      "option_b": "Paris",
      "option_c": "Berlin",
      "option_d": "Madrid",
      "correct_answer": "B",
      "difficulty": "easy",
      "related_exams_count": 2,
      "created_at": "2024-04-01T12:00:00Z",
      "created_by": { "id": "uuid", "full_name": "Staff Name" },
      "updated_at": "2024-04-02T10:00:00Z",
      "updated_by": "uuid"
    }
  ]
}
```

---

## 2. Create Question
**Endpoint:** `POST /v1/questions/`  
**Description:** Creates a new question and optionally adds it to multiple exams.  
**Permissions:** `ActiveModeratorPermissions` (Moderator, Admin, or Superadmin)

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `text` | String | **Required.** The question text. |
| `option_a` | String | **Optional.** Option A text. |
| `option_b` | String | **Optional.** Option B text. |
| `option_c` | String | **Optional.** Option C text. |
| `option_d` | String | **Optional.** Option D text. |
| `correct_answer` | String | **Required.** Correct choice (A, B, C, or D). |
| `difficulty` | String | **Optional.** (Default: moderate) Choices: easy, moderate, hard. |
| `add_to_exams` | Array (UUID) | **Optional.** List of exam IDs to immediately link this question to. |

```json
{
  "text": "New Question?",
  "option_a": "Ans A",
  "option_b": "Ans B",
  "option_c": "Ans C",
  "option_d": "Ans D",
  "correct_answer": "A",
  "difficulty": "moderate",
  "add_to_exams": ["uuid-exam-1"]
}
```

### Response Body
Returns the full question object (see **Get Question Details**).

---

## 3. Get Question Details
**Endpoint:** `GET /v1/questions/{question_id}/`  
**Description:** Retrieves detailed information about a single question, including related exams.  
**Permissions:** `ActiveModeratorPermissions` (Moderator, Admin, or Superadmin)

### Response Body
```json
{
  "id": 1,
  "text": "What is the capital of France?",
  "option_a": "London",
  "option_b": "Paris",
  "option_c": "Berlin",
  "option_d": "Madrid",
  "correct_answer": "B",
  "difficulty": "easy",
  "related_exams": [
    {
      "id": "uuid-exam-1",
      "title": "League Round 1",
      "description": "...",
      "stage": "league",
      "scheduled_date": "..."
    }
  ],
  "related_exams_count": 1,
  "created_at": "2024-04-01T12:00:00Z",
  "created_by": { "id": "uuid", "full_name": "Staff Name" },
  "updated_at": "...",
  "updated_by": "..."
}
```

---

## 4. Update Question
**Endpoint:** `PUT/PATCH /v1/questions/{question_id}/`  
**Description:** Updates an existing question.  
**Permissions:** `ActiveModeratorPermissions`

### Request Body
Fields same as **Create Question** (all optional for PATCH).

---

## 5. Delete Question
**Endpoint:** `DELETE /v1/questions/{question_id}/`  
**Description:** Archives a question by setting `is_archived` to true.  
**Permissions:** `ActiveModeratorPermissions`

---

## 6. Question-Exam Association
**Endpoint:** `POST /v1/questions/{question_id}/exams/`  
**Description:** Add or remove a single question from multiple exams.  
**Permissions:** `ActiveAdminPermissions` (Admin or Superadmin)

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `add_to_exams` | Array (UUID) | **Optional.** Exam IDs to add this question to. |
| `remove_from_exams` | Array (UUID) | **Optional.** Exam IDs to remove this question from. |

```json
{
    "add_to_exams": ["uuid-exam-1"],
    "remove_from_exams": ["uuid-exam-2"]
}
```

### Response Body
```json
{
    "question_id": 1,
    "added": [ { "exam_id": "...", "exam_title": "..." } ],
    "removed": [ { "exam_id": "...", "exam_title": "..." } ],
    "failed_additions": [],
    "failed_removals": []
}
```

---

## 7. Bulk Add Questions to Exams
**Endpoint:** `POST /v1/questions/bulk-add-to-exams/`  
**Description:** Add multiple questions to multiple exams in one operation.  
**Permissions:** `ActiveAdminPermissions`

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `question_ids` | Array (Integer) | **Required.** List of question IDs. |
| `exam_ids` | Array (UUID) | **Required.** List of exam IDs. |

```json
{
    "question_ids": [1, 2, 3],
    "exam_ids": ["uuid-exam-1", "uuid-exam-2"]
}
```

### Response Body
```json
{
    "summary": {
        "total_operations": 6,
        "successful": 6,
        "skipped": 0,
        "failed": 0
    },
    "details": {
        "added": [...],
        "skipped": [...],
        "failed_questions": [...],
        "failed_exams": [...]
    }
}
```

---

## 8. Bulk Archive Questions
**Endpoint:** `POST /v1/questions/bulk-archive/`  
**Description:** Archive multiple questions in one operation.  
**Permissions:** `ActiveAdminPermissions`

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `question_ids` | Array (Integer) | **Required.** List of question IDs to archive. |

```json
{
    "question_ids": [1, 2, 3]
}
```

### Response Body
```json
{
    "summary": {
        "total_questions": 3,
        "successful_archives": 3,
        "failed_archives": 0
    },
    "details": {
        "archived": [1, 2, 3],
        "failed": []
    }
}
```

---

## 9. List Exam Questions (V2)
**Endpoint:** `GET /v2/exams/{exam_id}/questions/`  
**Description:** Returns all questions belonging to a specific exam.  
**Permissions:** `ActiveAdminPermissions`

### Response Body
```json
[
  {
    "id": 1,
    "text": "Question text",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_answer": "A",
    "difficulty": "moderate",
    "related_exams_count": 1,
    "created_at": "...",
    "created_by": { ... },
    "updated_at": "...",
    "updated_by": "..."
  }
]
```
