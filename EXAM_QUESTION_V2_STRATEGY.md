# Exam & Question Management V2 Strategy

This document outlines the strategy for upgrading Exam and Question management to V2, focusing on performance, consistency, and automated cache management.

## 1. Core Principles
- **Centralized Logic**: Move business rules (like "who can edit an exam") from views into services or model-level validation.
- **Cache-First Architecture**: Use the `CacheKeys` utility for all GET operations.
- **Signal-Driven Invalidation**: Automatically clear relevant caches on `post_save` and `post_delete`.
- **Bulk Safety**: Ensure bulk operations (adding questions to exams) are transactional and atomic.

---

## 2. Question Management V2

Currently, question management is partially in V1. We will consolidate it in `vmlc/v2/`.

### A. New Serializers (`vmlc/v2/serializers/question.py`)
- **QuestionV2Serializer**: Unified serializer for List/Retrieve/Create/Update.
- **QuestionBulkActionSerializer**: Handles lists of IDs for batch archiving or exam assignment.

### B. New Views (`vmlc/v2/views/question.py`)
- **QuestionListCreateV2View**: 
    - Implements advanced filtering (by difficulty, creator, or "not in exam X").
    - Uses `question_pool_data` caching with automatic invalidation.
- **QuestionDetailV2View**:
    - Includes `related_exams` with full competition context.
- **Bulk Operations**:
    - `POST /v2/questions/bulk-archive/`
    - `POST /v2/questions/bulk-assign/` (Assign multiple questions to multiple exams).

---

## 3. Exam Management V2 (Refinement)

Already existing in `vmlc/v2/views/exam.py`, but needs the following upgrades:

### A. Serializer Upgrades (`vmlc/v2/serializers/exam.py`)
- **Automatic Slotting**: Improve `_handle_competition_slot` to better support the `StageExam` model.
- **Validation**: Strict validation to prevent editing `CONCLUDED` or `ONGOING` exams.
- **RankingSnapshot Integration**: Directly show if ranking_snapshot are generated/published.

### B. View Upgrades (`vmlc/v2/views/exam.py`)
- **Caching**: Wrap all `list()` and `retrieve()` calls in `get_or_set_cache`.
- **Performance**: Use `.annotate(question_count=...)` and `.select_related()` to avoid N+1 queries.

---

## 4. Cache Invalidation Matrix

| Action | Affected Cache Keys |
| :--- | :--- |
| **Create/Update Question** | `question_pool_data`, `exam_questions_{id}`, `dash:staff:global` |
| **Assign Q to Exam** | `exam_questions_{id}`, `exam_detail:{id}`, `dash:staff:global` |
| **Conclude Exam** | `exam_detail:{id}`, `dash:staff:global`, `dash:cand:{all}` |
| **Publish RankingSnapshot** | `exam_results:{id}`, `lb:league:latest`, `dash:cand:{all}` |

---

## 5. Implementation Roadmap

1.  **Step 1: Questions V2 Migration**:
    - Create `vmlc/v2/serializers/question.py`.
    - Create `vmlc/v2/views/question.py` (migrating and cleaning up V1 logic).
2.  **Step 2: Exam V2 Refinement**:
    - Update `ExamDetailV2Serializer` validation logic.
    - Integrate `CacheKeys` into `ExamListV2View` and `ExamDetailV2View`.
3.  **Step 3: Signal Finalization**:
    - Ensure `vmlc/signals.py` covers all Queston/Exam M2M relationship changes.
4.  **Step 4: URL Cleanup**:
    - Move all staff-facing exam/question endpoints under `/v2/`.
