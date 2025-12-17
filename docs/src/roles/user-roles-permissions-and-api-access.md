# User Roles, Permissions, and API Access


This table provides a detailed breakdown of each user role, its key abilities on the platform, and the primary API endpoints it has access to.

### Candidate User Type

| Role | Key Abilities (What they can do) | Accessible API Endpoints |
|------|-----------------------------------|--------------------------|
| **`screening`** | • View their personal dashboard.<br>• Take screening-level exams.<br>• View their own profile and verification status.<br>• View screening leaderboard snapshots. | • `GET /dashboard/candidate/`<br>• `GET /candidates/me/`<br>• `GET /user/verification/status/`<br>• `POST /user/verification/upload/`<br>• `GET /exams/{id}/take-exam/` (where `stage` is `screening`)<br>• `POST /exams/{id}/submit-exam-answers/`<br>• `GET /leaderboard/` (for screening exams) |
| **`league`** | • All `screening` abilities.<br>• Take league-level exams.<br>• View the competition leaderboard snapshots or a specific exam leaderboard. | • All `screening` endpoints.<br>• `GET /leaderboard/`<br>• `GET /exams/{id}/take-exam/` (where `stage` is `league`) |
| **`final`** | • All `league` abilities.<br>• Access to (offline) final-stage exams. | • All `league` endpoints.<br>• `GET /exams/{id}/take-exam/` (where `stage` is `final`) |
| **`winner`** | • Ceremonial role with all candidate permissions. Registered winner of the final stage. | • All `final` endpoints. |

### Staff User Type

*(Permissions are hierarchical; higher roles inherit permissions from lower roles)*

| Role | Key Abilities (What they can do) | Newly Accessible API Endpoints (in addition to lower roles) |
|------|-----------------------------------|-------------------------------------------------------------|
| **`volunteer`** | • View their own profile.<br>• Submit their own documents for verification. | • `GET /staff/me/`<br>• `GET /user/verification/status/`<br>• `POST/PATCH /user/verification/upload/` |
| **`admin`** | • View details for any candidate.<br>• Change roles for candidates.<br>• Full management (CRUD) of exams.<br>• Manually submit scores.<br>• Publish leaderboard for a specific exam. | • `GET /candidates/{id}/`<br>• `GET /candidates/{id}/scores/`<br>• `GET /candidates/{id}/exam-history/`<br>• `PUT /candidates/{id}/roles/assign/`<br>• `GET/POST /exams/`<br>• `GET/PUT/PATCH/DELETE /exams/{id}/`<br>• `PUT /exams/{id}/submit-exam-score/`<br>• `POST /leaderboard/publish/` |
| **`manager`** | • View details for any staff member.<br>• Change roles for staff (except `manager` or `superadmin`).<br>• Manage user verifications for candidates and staff members (approve/reject).<br>• Create and view broadcasts. | • `GET /staff/{id}/`<br>• `PUT /staff/{id}/roles/assign/`<br>• `GET /user/verification/list/`<br>• `POST /user/verification/action/{id}/`<br>• `GET /user/verification/documents/{type}/{id}/`<br>• `GET/POST /broadcasts/`<br>• `GET /broadcasts/{id}/`<br>• `GET/PATCH /account-management/{id}/` |
| **`superadmin`** | • Can assign any staff role (except `superadmin`).<br>• Has full platform control inheriting all permissions. | *(Inherits all `manager` endpoints with zero restrictions)* |
| **`sponsor`** | • A vanity role with no specific permissions. | *(No specific endpoints)* |

**NOTE**: Users must already have their emails verified and be user-verified to perform actions beyond `get-started`.

#### Role Progression
- **Candidates**: `screening` → `league` → `final` → `winner` (progression is managed by staff with `admin` role or higher)
- **Staff**: Roles are assigned by a `manager` or `superadmin`.

---
