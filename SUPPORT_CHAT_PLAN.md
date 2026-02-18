## CONTEXT

We are building a real-time in-app support chat system inside a Django project.

Stack:

* Django
* Django REST Framework
* Django Channels (already configured)
* Redis (channel layer + caching)
* Celery (for async tasks)
* PostgreSQL
* ~400 concurrent candidates during peak exam sessions

Existing:

* Channels is already used for real-time notifications
* Redis is already running
* Authentication is token-based
* Users have roles (candidate, staff/moderator/admin)
* Staff permissions handled via custom permission classes

Goal:
Build a persistent, global 1:1 support chat per candidate account.

This is NOT a ticketing system.
This is a continuous support thread per candidate.

---

# REQUIREMENTS

---

## 1️⃣ Data Models

Implement the following models:

### SupportThread

Fields:

* candidate (FK to User, unique=True)
* assigned_staff (FK to StaffProfile, nullable=True)
* last_message_at (DateTimeField, indexed)
* created_at
* updated_at

Indexes:

* last_message_at
* assigned_staff

Constraints:

* One thread per candidate (unique constraint)

---

### ThreadMessage

Fields:

* thread (FK to SupportThread, related_name="messages")
* sender (FK User, nullable=True)
* sender_type (choices: candidate, staff, system)
* text (TextField)
* metadata (JSONField, nullable=True, blank=True)
* created_at (auto_now_add=True, indexed)

---

### MessageRead

Fields:

* message (FK ThreadMessage, related_name="reads")
* user (FK User)
* read_at (auto_now_add=True)

Unique constraint:

* (message, user)

---

## 2️⃣ REST API Endpoints

Implement:

### A. Get or Create Thread (Candidate)

GET /support/thread/

* If thread exists for authenticated candidate → return it
* If not → create it
* If created → insert system message:
  "Hiii {full_name}! How can we help you today?"

---

### B. Post Message

POST /support/thread/{thread_id}/message/

* Validate user is either:

  * Thread owner
  * Staff
* Save ThreadMessage
* Update thread.last_message_at
* Trigger escalation check task if sender_type == candidate
* Broadcast message via WebSocket group

---

### C. Staff Thread List

GET /staff/support/threads/

Return threads ordered by:

1. Unread count (desc)
2. Candidate online status (online first)
3. last_message_at (desc)

Use efficient prefetching to avoid N+1 queries.

---

## 3️⃣ WebSocket Layer (Django Channels)

Implement a WebSocket consumer:

Group naming:
support_thread_{thread_id}

Events:

### A. message

Broadcast when new message is created

Payload:
{
type: "chat.message",
message: serialized_message
}

---

### B. typing

Payload:
{
type: "chat.typing",
user_id: X,
is_typing: true/false
}

Typing indicators:

* Do NOT persist in DB
* Broadcast only

---

## 4️⃣ Presence Detection (Redis-Based)

On WebSocket connect:

* SET user_online_{user_id} = 1 with 60-second TTL

Every 30 seconds:

* Refresh TTL

On disconnect:

* DELETE key

Staff dashboard must:

* Check Redis for online presence
* Expose online status in thread list serializer

DO NOT store presence in database.

---

## 5️⃣ Auto Escalation (2-Minute Rule)

When candidate sends message:

* Schedule Celery task with ETA = message.created_at + 2 minutes

Task logic:

* Fetch latest message in thread
* If latest message sender_type == "candidate":

  * Trigger escalation:

    * Send email and SMS to admins & managers
    * Send Slack alert
  * Optionally flag thread as urgent

Do NOT use time.sleep().
Use ETA scheduling.

---

## 6️⃣ Staff Load Balancing

When:

* A thread has no assigned_staff
* And first staff reply occurs

Assign thread automatically using:

* Get active staff
* Annotate with active thread count
* Assign to staff with lowest load

Query must be optimized.

---

## 7️⃣ Read Tracking

When user opens thread:

* Bulk create MessageRead for all unread messages
* Use ignore_conflicts=True

Unread count must be computed relationally:
thread.messages.exclude(reads__user=request.user).count()

Must use prefetch_related("messages__reads") in list views.

---

## 8️⃣ Performance Requirements

Must support:

* 400 concurrent candidates
* Efficient WebSocket group handling
* No N+1 queries
* Redis-backed presence
* Indexed timestamp queries

---

## 9️⃣ Security

* Users can only access their own thread
* Staff can access all threads
* WebSocket connection must validate authentication
* Thread group join must validate membership

---

## 10️⃣ Future-Proofing

ThreadMessage.metadata should allow:

* exam_id
* exam_status
* device info
* connection quality

Design with forward compatibility in mind.

---

# OUTPUT EXPECTATION

The implementation must include:

* Models
* Migrations
* Serializers
* REST Views
* WebSocket Consumer
* Celery Task
* Redis presence utilities
* Proper indexes
* Efficient queryset usage
* Clear comments

Code must be production-grade and scalable.
