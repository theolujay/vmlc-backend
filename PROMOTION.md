# Promotion & Ranking API Documentation

This documentation is intended for frontend developers integrating the competition management and candidate progression features.

---

## 1. Generate Ranking Snapshot
**Endpoint:** `POST /v1/competition/rankings/publish/`  
**Description:** Finalizes exam scores and calculates the leaderboard ranks for a specific exam. This must be called after an exam concludes before candidates can be promoted to the next stage.

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `exam_id` | UUID | **Required.** The UUID of the concluded exam. |
| `publish_now` | Boolean | **Optional.** (Default: false). If `true`, the rankings become visible to candidates immediately. If `false`, staff can review them in the dashboard before publishing. |

### Client Integration Notes
- **Usage**: Trigger this action from the Staff Dashboard once an exam's status changes to `concluded`.
- **Status Code `202 Accepted`**: This is an asynchronous operation. The API will return immediately while processing scores and ranks in the background.
- **UI Feedback**: After receiving a `202`, the UI should indicate that processing is underway. The "Ranking Status" for this exam in the staff dashboard will eventually transition from `pending` to `ready` (or `published` if `publish_now` was true).
- **Side Effects**: When complete, this clears the cached dashboard data for all affected candidates.

---

## 2. Advance Candidates (Promotion)
**Endpoint:** `POST /v1/competition/promote/`  
**Description:** Moves a batch of candidates from their current stage to the next (e.g., advancing the top performers from "Screening" to "League").

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `from_stage` | String | **Required.** Source stage (`screening` or `league`). |
| `to_stage` | String | **Required.** Target stage (`league` or `final`). |
| `cutoff_rank` | Integer | **Optional.** The rank threshold (e.g., top 100). If omitted, the API uses the pre-configured advancement policy for that stage. |

### Client Integration Notes
- **Pre-requisite**: This should only be called after the relevant Ranking Snapshot or Leaderboard has been generated and reviewed.
- **UI Workflow**:
    1. Staff selects the stages and optionally enters a cutoff.
    2. API processes the batch update.
    3. Success message indicates the number of candidates advanced.
- **Impact on Candidates**:
    - **Permissions**: Promoted candidates immediately gain access to the new stage's resources (e.g., upcoming League exams).
    - **Notifications**: Candidates receive an automated in-app notification (Success/Info type) regarding their new status.
    - **Dashboard Change**: The candidate's "Stage Progress" UI will update to reflect their new stage or eliminated status.

---

## Expected Status & Error Handling

### Common Response Codes
- `200 OK`: Operation successful (used for promotion).
- `202 Accepted`: Request accepted for background processing (used for ranking generation).
- `400 Bad Request`: Validation error (e.g., trying to generate rankings for an exam that hasn't finished yet).
- `403 Forbidden`: Authenticated user does not have required permissions (Staff/Manager role required).

### Sample Error Response
```json
{
  "status": "error",
  "message": "No published rankings found for the source stage."
}
```