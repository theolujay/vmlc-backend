# QR-Based Security for Final Exams (Backend Implementation)

## 1. WebSocket Infrastructure Extension

The backend will leverage the existing `UnifiedConsumer` and `channel_layer` to bridge the communication between Admin and Candidate.

### New WebSocket Action: `unlock_exam`
- **Location**: `comms/consumers.py` within the `UnifiedConsumer.receive_json` method.
- **Access Control**:
    - Verify that the calling user has `staff.role` in `['admin', 'manager', 'superadmin']`.
- **Logic**:
    1. Receive `candidate_id` and `exam_id` from the Admin's payload.
    2. Validate that the `exam_id` belongs to an exam with `delivery_mode="in_person"` or is linked to a `FINAL` stage.
    3. Retrieve the target candidate's channel group: `user__{candidate_id}`.
    4. Use `self.channel_layer.group_send` to broadcast an `exam.unlocked` event to that group.

```python
# Example logic in UnifiedConsumer
elif action == "exam.unlock_request":
    if not self.is_staff_admin: # Custom check for Admin role
        await self.send_error("Unauthorized to unlock exams")
        return

    candidate_id = data.get("candidate_id")
    exam_id = data.get("exam_id")

    # Broadcast to candidate
    await self.channel_layer.group_send(
        f"user__{candidate_id}",
        {
            "type": "exam.unlocked",
            "data": {
                "exam_id": exam_id,
                "unlocked_by": str(user.id)
            }
        }
    )
```

## 2. Real-time Broadcasting
- **Message Type**: `exam.unlocked`
- **Handler**: A new handler method `async def exam_unlocked(self, event)` will be added to `UnifiedConsumer`.
- **Payload**: Contains the `exam_id` and a confirmation timestamp.
<!-- 
## 3. Database & Persistence (Tentative)
To prevent candidates from bypassing the QR screen by refreshing the page, we should persist the "unlocked" status for the duration of the exam attempt.
- **Model Update**: Add `is_unlocked` and `unlocked_by` BooleanField(s) to the `ExamAccess` or any other preferrable model.
- **Validation**: When the candidate hits the `START/RESUME` endpoint, check if `is_unlocked` is `True` if the exam is an in-person final. -->

## 4. Security Considerations
- **Admin Verification**: Only Admins can trigger the unlock signal.
- **Scope Limitation**: The unlock signal only works for the specific `candidate_id` scanned.
- **QR Integrity**: The QR payload should ideally include a short-lived HMAC or signature to prevent candidates from generating their own "unlock" payloads (though the current flow relies on Admin scanning, which is inherently secure).
- **Stage Check**: Explicitly verify that the exam is a `FINAL` stage exam before allowing the unlock logic to trigger.

## 5. Ongoing Monitoring
- Admin should be able to see a "Session Unlocked" status in their management dashboard for that specific candidate to confirm the scan was successful.
