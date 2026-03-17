# How the Heartbeat Feature Works

## What is a Heartbeat?

A heartbeat is a periodic signal that the exam page sends to the server to report what's happening during an exam. Think of it like a check-in: every few minutes, the page says "Hey, I'm still here, and here's what happened since the last check-in."

## Why Do We Need It?

During an exam, the proctoring system needs to know:

- Is the student still taking the exam?
- Did they do anything suspicious (like switching tabs, looking away, or having multiple faces in the camera)?
- What was the environment like (browser, screen size, etc.)?

The heartbeat carries all this information to the server.

## How It Works (Simple Version)

```
┌─────────────────────────────────────────────────────────────────┐
│                         EXAM PAGE                               │
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│   │  Tab Switch │    │ Face Detect │    │  ...other   │       │
│   │  Detector   │    │   Detector  │    │  detectors  │       │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘       │
│          │                  │                  │               │
│          └──────────────────┼──────────────────┘               │
│                             ▼                                   │
│                    ┌──────────────┐                            │
│                    │ Violation    │                            │
│                    │ Manager      │                            │
│                    │ (stores      │                            │
│                    │  counts)     │                            │
│                    └──────┬───────┘                            │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                 │
│         ▼                 ▼                 ▼                 │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐           │
│   │ Every 5  │      │   Send   │      │   Take   │           │
│   │ minutes  │ ──▶  │ Heartbeat │ ──▶  │ Screenshot│          │
│   └──────────┘      └──────────┘      └──────────┘           │
│                            │                                   │
└────────────────────────────┼───────────────────────────────────┘
                             ▼
                    ┌────────────────┐
                    │    SERVER      │
                    │                │
                    │  - Validates   │
                    │  - Stores data │
                    │  - Calculates  │
                    │    suspicion   │
                    └────────────────┘
```

## Step-by-Step Flow

### 1. During the Exam

The exam page runs several "detectors" in the background:

| Detector     | What it watches for                          |
| ------------ | -------------------------------------------- |
| Tab Switch   | User switching to another browser tab/window |
| Face Proctor | No face, multiple faces, or looking away     |
| Fullscreen   | User exiting fullscreen mode                 |
| DevTools     | User opening browser developer tools         |

Whenever a detector notices something, it calls `reportViolation()`.

### 2. Recording Violations

When `reportViolation("NO_FACE")` is called:

```
reportViolation("NO_FACE")
         │
         ▼
┌─────────────────────┐
│ Violation Manager   │
│                     │
│ summaryRef = {      │
│   NO_FACE: 1,       │  ← Increment counter
│   TAB_SWITCH: 0,    │
│   ...               │
│ }                   │
│                     │
│ eventsRef = [       │
│   {type: "NO_FACE", │  ← Store event details
│    timestamp: ...}  │
│ ]                   │
└─────────────────────┘
```

### 3. Sending the Heartbeat

Every 5 minutes (1 minute in development), the heartbeat is sent:

```
┌────────────────────────────────────┐
│         HEARTBEET PAYLOAD          │
├────────────────────────────────────┤
│ sequence_number: 1, 2, 3, ...     │  ← Counts up each time
│ period_start: "10:00"              │  ← When this period began
│ period_end: "10:05"                │  ← When we sent this
│                                     │
│ summary: {                         │  ← Total counts since last heartbeat
│   NO_FACE: 12,                     │
│   TAB_SWITCH: 3,                   │
│   ...                              │
│ }                                  │
│                                     │
│ events: [                          │  ← Individual event details
│   {type: "NO_FACE", time: "10:02"}│
│ ]                                  │
│                                     │
│ meta: {                            │  ← Browser/device info
│   browser: "Chrome",                │
│   os: "Windows",                   │
│   screen: "1920x1080"              │
│ }                                  │
└────────────────────────────────────┘
```

### 4. After Sending

Once the heartbeat is sent successfully:

- The counters reset to zero
- The events list clears
- The sequence number increases

This starts fresh for the next 5-minute period.

## Key Components

### `useViolationManager` Hook

This is the central piece that:

1. Stores violation counts (in a `ref` for reliability)
2. Collects event details
3. Sends heartbeats on a timer
4. Handles retry if heartbeat fails

### `FaceProctor` Component

Uses the camera to detect faces. Calls `reportViolation("NO_FACE")` when no face is seen.

### Why Use a `ref` Instead of State?

We use `useRef` for the violation summary because:

- The heartbeat timer runs asynchronously
- Regular `useState` can have "stale" values in callbacks
- A `ref` always gives you the current value instantly

This prevents violations from being lost between heartbeats.

## What Happens on the Server?

1. Receives the heartbeat payload
2. Validates the sequence number (no gaps?)
3. Stores the data
4. Calculates a "suspicion score" based on violations
5. Updates the exam's proctoring status

## Violation Types & Weights

| Violation       | Weight | Meaning                |
| --------------- | ------ | ---------------------- |
| TAB_SWITCH      | 0.3    | Left the exam tab      |
| NO_FACE         | 0.2    | Not in front of camera |
| MULTI_FACE      | 0.5    | Someone else in frame  |
| FULLSCREEN_EXIT | 0.1    | Left fullscreen        |
| DEVTOOLS_OPEN   | 0.4    | Trying to inspect code |
| SCREENSHOT      | 0.1    | Took a screenshot      |

The suspicion score is the weighted sum, capped at 1.0.
