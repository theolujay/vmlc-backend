# Dynamic Performance Dashboard Improvements

The current implementation of the `Performance` component relies on a hardcoded `STAGE_CONFIG` object and complex client-side logic in `ExamPortal.tsx`. To make the dashboard more flexible and reduce frontend maintenance, the candidate dashboard API (`/candidate/dashboard/`) is being improved to provide pre-computed metadata.

## Backend Reference: STAGE_METADATA
The following metadata structure is implemented in the backend to drive the dashboard dynamically:

```python
STAGE_METADATA = {
    Stage.Type.SCREENING: {
        "label": "Screening Stage",
        "accent_color": "#4F46E5",
        "metric_label": "League Qualification Cut-off",
        "status_messages": {
            "success": {"label": "Within Qualification Range", "subtext": "Maintaining this position keeps you eligible for the League stage."},
            "pending": {"label": "Results Pending", "subtext": "Your performance is being evaluated. Check back soon for your official ranking."},
            "error": {"label": "Below Qualification Range", "subtext": "Unfortunately, you didn't meet the cutoff for the League stage."},
            "warning": {"label": "Action Required", "subtext": "You haven't participated in this stage yet."},
        },
    },
    Stage.Type.LEAGUE: {
        "label": "League Stage",
        "accent_color": "#3E4095",
        "metric_label": "Finalist Qualification Cut-off",
        "status_messages": {
            "success": {"label": "Within Qualification Range", "subtext": "Maintaining this position keeps you eligible for the Grand Final."},
            "pending": {"label": "Results Pending", "subtext": "Round results are being processed."},
            "error": {"label": "Below Qualification Range", "subtext": "Current ranking is outside the Finalist qualification range."},
            "warning": {"label": "Round Ongoing", "subtext": "Complete your rounds to maintain your leaderboard position."},
        },
    },
    Stage.Type.FINAL: {
        "label": "Grand Final",
        "accent_color": "#D97706",
        "metric_label": "Champion Threshold",
        "status_messages": {
            "success": {"label": "Champion Material", "subtext": "Top performance in the Grand Final!"},
            "pending": {"label": "Results Pending", "subtext": "The final ranking is being verified."},
            "error": {"label": "Finalist", "subtext": "Congratulations on reaching the Grand Final!"},
            "warning": {"label": "Showtime", "subtext": "The Grand Final is here. Give it your best shot!"},
        },
    },
}
```

## Finalized Backend Implementation: STAGE_METADATA

This complete dictionary should be implemented in the backend. It provides the source of truth for all labels, accents, and status-specific styling for the Performance component.

```python
STAGE_METADATA = {
    "SCREENING": {
        "label": "Screening Stage",
        "accent_color": "#4F46E5",
        "metric_label": "League Qualification Cut-off",
        "status_messages": {
            "success": {
                "label": "Screening Passed",
                "subtext": "You are eligible for promotion to the League stage.",
                "color": "#018ABB",
                "bg_color": "#CCEEFB33",
                "icon": "check"
            },
            "pending": {
                "label": "Awaiting Results",
                "subtext": "Your performance is being evaluated. Results will be available soon.",
                "color": "#065F46",
                "bg_color": "#ECFDF5",
                "icon": "clock"
            },
            "error": {
                "label": "Screening Not Passed",
                "subtext": "Your score did not meet the required cut-off for promotion.",
                "color": "#CB1A14",
                "bg_color": "#FBEAE9",
                "icon": "alert"
            },
            "warning": {
                "label": "Screening Upcoming",
                "subtext": "The screening examination hasn't yet commenced. Please await updates.",
                "color": "#667185",
                "bg_color": "#F9FAFB",
                "icon": "calendar"
            }
        }
    },
    "LEAGUE": {
        "label": "League Stage",
        "accent_color": "#3E4095",
        "metric_label": "Finalist Qualification Cut-off",
        "status_messages": {
            "success": {
                "label": "Within Qualification Range",
                "subtext": "Maintaining this position keeps you eligible for the Grand Final.",
                "color": "#018ABB",
                "bg_color": "#CCEEFB33",
                "icon": "check"
            },
            "pending": {
                "label": "Results Pending",
                "subtext": "The leaderboard is being updated with the latest scores. Check back soon.",
                "color": "#065F46",
                "bg_color": "#ECFDF5",
                "icon": "clock"
            },
            "error": {
                "label": "Outside Qualification Range",
                "subtext": "Improved performance is advised in upcoming rounds to reach the Final stage.",
                "color": "#CB1A14",
                "bg_color": "#FBEAE9",
                "icon": "alert"
            },
            "warning": {
                "label": "Round Assessment Pending",
                "subtext": "The assessment for the current round has not started yet. Prepare well!",
                "color": "#667185",
                "bg_color": "#F9FAFB",
                "icon": "calendar"
            }
        }
    },
    "FINAL": {
        "label": "Grand Final",
        "accent_color": "#D97706",
        "metric_label": "Champion Threshold",
        "status_messages": {
            "success": {
                "label": "Finalist Confirmed",
                "subtext": "You are cleared to participate in the in-person final examination.",
                "color": "#018ABB",
                "bg_color": "#CCEEFB33",
                "icon": "check"
            },
            "pending": {
                "label": "Under Review",
                "subtext": "Final results are being verified. An official broadcast will follow shortly.",
                "color": "#065F46",
                "bg_color": "#ECFDF5",
                "icon": "clock"
            },
            "error": {
                "label": "Final Status Pending",
                "subtext": "Your participation requires further review by the organizers.",
                "color": "#CB1A14",
                "bg_color": "#FBEAE9",
                "icon": "alert"
            },
            "warning": {
                "label": "Finals Upcoming",
                "subtext": "The final examination schedule and details will be shared soon.",
                "color": "#667185",
                "bg_color": "#F9FAFB",
                "icon": "calendar"
            }
        }
    }
}
```

## Proposed API Improvements

The API should return an `active_context` object that encapsulates both the user's data and the metadata required for display, mapped from the `STAGE_METADATA` above.

### 1. Unified Performance Context
Instead of separate ranking objects, the API will identify the **active stage** and return a focused context:

```json
{
  "performance": {
    "active_context": {
      "stage": "LEAGUE",
      "stage_display": "League Stage",
      "title": "League Performance • Round 3 of 6",
      "accent_color": "#3E4095",
      "ranking": {
        "position": 42,
        "total_candidates": 1200,
        "rank_change": 5,
        "score": 850,
        "percentile": 96.5,
        "is_active": true
      },
      "status_meta": {
        "status_type": "success",
        "metric_label": "Finalist Qualification Cut-off",
        "metric_value_display": "Top 100",
        "status_label": "Within Qualification Range",
        "status_subtext": "Maintaining this position keeps you eligible for the Grand Final."
      }
    }
  }
}
```

### 2. Benefits of the Alignment
- **Source of Truth**: The `accent_color`, `metric_label`, and status messages are managed in one place (the backend), ensuring consistency across all platforms (Web, Mobile, etc.).
- **Dynamic Context**: The `status_type` (success, pending, error, warning) is determined by the backend logic, allowing it to account for "awaiting results" or "not participated" states automatically.
- **Surgical Frontend**: The `Performance` component will no longer need internal `STAGE_CONFIG` constants or complex conditional rendering logic.

## Color Alignment & UI Consistency
The backend `accent_color` values currently deviate from the existing frontend implementation for Screening and Final stages. To ensure a polished UI, we should decide whether to adopt the new backend colors or update the backend to match the established frontend palette.

| Stage | Frontend (Current) | Backend (Draft) | Action |
| :--- | :--- | :--- | :--- |
| **SCREENING** | `#01ACEA` (Cyan) | `#4F46E5` (Indigo) | Review Required |
| **LEAGUE** | `#3E4095` (Deep Blue) | `#3E4095` (Deep Blue) | Matches |
| **FINAL** | `#099137` (Green) | `#D97706` (Amber) | Review Required |

### Enhancing Status Metadata
To fully decouple the frontend, the `status_messages` should ideally include styling hints (colors and icons). This prevents the frontend from hardcoding "Success = Green" when a stage might require a different semantic color.

**Recommended Metadata Expansion:**
```python
"status_messages": {
    "success": {
        "label": "Within Qualification Range",
        "subtext": "...",
        "color": "#059669", # Emerald-600
        "bg_color": "#ECFDF5", # Emerald-50
        "icon": "check-circle"
    },
    # ... other statuses
}
```

## Implementation Strategy

1. **Update `DashboardType`**: Extend the TypeScript types in `src/types/Examtype.ts` to match the `active_context` and `status_meta` structures.
2. **Refactor `Performance.tsx`**: Modify the component to consume the `active_context` directly, using `status_meta` for all banners and labels.
3. **Simplify `ExamPortal.tsx`**: Remove the manual mapping of thresholds, stage selection, and "awaiting results" flags.
