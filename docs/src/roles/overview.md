# User Roles & Permissions

The VMLC API implements a comprehensive role-based access control (RBAC) system with two user types: **Candidates** and **Staff**.

## User Types

### Candidates

Students participating in the mathematics competition. They progress through different competition stages.

**Roles:** `screening` → `league` → `final` → `winner`

### Staff

Team members who manage the competition platform, from content creation to user verification.

**Roles:** `volunteer` → `moderator` → `admin` → `manager` → `superadmin`

## Key Concepts

### Role Hierarchy

- Permissions are hierarchical
- Higher roles inherit permissions from lower roles
- Role changes are managed by authorized staff

### Verification

- Users must verify their email before accessing most features
- Document verification is required for role promotion
- Verification is managed by staff with appropriate permissions

## Learn More

- [Candidate Roles](candidate-roles.md) - Detailed candidate role information
- [Staff Roles](staff-roles.md) - Detailed staff role information
- [Feature Walkthroughs](feature-walkthroughs-and-user-stories.md) - Real-world usage scenarios
