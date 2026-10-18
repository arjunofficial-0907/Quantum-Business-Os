# Quantum Business OS — Domain Model

**Document:** Domain Model  
**Phase:** Phase 1 — Platform Foundation  
**Status:** Architecture Draft — Day 1  
**Scope:** Core Platform

---

## 1. Purpose

This document defines the core domain model for Quantum Business OS.

The domain model must support:

- single-branch businesses
- multi-branch businesses
- multiple users
- role-based access control
- subscriptions
- billing
- auditability
- offline-first desktop operation
- future web and mobile applications
- future business verticals beyond restaurants

The Core Platform must remain independent of the Restaurant Module.

---

# 2. Core Domain Hierarchy

The fundamental business hierarchy is:

Organization
└── Branch

A single-branch customer:

Organization
└── Branch

A multi-branch customer:

Organization
├── Branch 1
├── Branch 2
└── Branch N

There is no separate architecture for single-branch and multi-branch customers.

---

# 3. Identity Model

## 3.1 User

A User represents a human identity in Quantum Business OS.

A User does not inherently belong to a single organization.

Conceptually:

User
├── id
├── email
├── password_hash
├── status
├── created_at
└── updated_at

The User entity represents identity.

It does not determine business permissions by itself.

---

# 4. Organization

An Organization represents a customer/business account.

Examples:

- ABC Cafe
- ABC Foods Pvt Ltd
- XYZ Restaurant Group

Organization is the primary SaaS tenant.

Conceptually:

Organization
├── id
├── name
├── legal_name
├── status
├── created_at
└── updated_at

Organization-level data may include:

- subscription
- billing
- organization settings
- branding
- organization-wide permissions
- organization-wide reporting configuration

---

# 5. Branch

A Branch represents an operational/business location belonging to an Organization.

Conceptually:

Organization
├── Branch
├── Branch
└── Branch

Branch-specific data may include:

- operational settings
- staff assignments
- orders
- tables
- inventory
- branch reports
- POS configuration

Every branch belongs to exactly one organization.

---

# 6. Membership

Membership connects a User to an Organization.

This relationship is intentionally separate from User.

Conceptually:

User
└── Membership
       └── Organization

A user may have memberships in multiple organizations.

Example:

User A
├── Membership → Organization A
└── Membership → Organization B

Membership may contain:

- id
- user_id
- organization_id
- status
- joined_at
- invited_by
- created_at
- updated_at

Membership is a central authorization boundary.

---

# 7. Role

A Role represents a named collection of permissions.

Examples:

- Owner
- Administrator
- Manager
- Cashier
- Staff

Roles should be data-driven rather than hard-coded application conditions.

Example:

Manager
├── orders.view
├── orders.create
├── orders.cancel
├── inventory.view
└── reports.view

---

# 8. Permission

A Permission represents one specific capability.

Permission naming convention:

resource.action

Examples:

users.view
users.create
users.update
users.delete

branches.view
branches.create
branches.update
branches.delete

orders.view
orders.create
orders.cancel

reports.view

Permissions should remain granular enough to support future business modules.

---

# 9. Role Assignment

Roles are assigned through the organization membership context.

Conceptually:

User
│
▼
Membership
│
▼
Role
│
▼
Permission

This prevents the User entity from becoming tightly coupled to one organization's authorization model.

---

# 10. Organization-Level and Branch-Level Access

Not every permission necessarily applies to every branch.

The architecture must eventually support access scopes.

Potential scopes:

- organization
- branch
- global/platform

Example:

A restaurant owner may have access to:

Organization
├── Branch A
├── Branch B
└── Branch C

A branch manager may only have access to:

Branch B

The backend must enforce these boundaries.

The desktop UI must never be considered the security boundary.

---

# 11. Subscription Plan

A SubscriptionPlan defines the commercial capabilities available to customers.

Initial plans:

- Starter
- Standard
- Premium
- Enterprise

A plan may define:

- price
- billing interval
- feature entitlements
- usage limits
- status

Example conceptual structure:

SubscriptionPlan
├── id
├── name
├── description
├── billing_interval
├── price
├── currency
├── features
├── limits
├── status
├── created_at
└── updated_at

---

# 12. Subscription

A Subscription represents an Organization's active commercial relationship with a SubscriptionPlan.

Relationship:

Organization
└── Subscription
       └── SubscriptionPlan

Subscription should support lifecycle states such as:

- trial
- active
- past_due
- paused
- cancelled
- expired

Exact states will be finalized during implementation.

---

# 13. Billing

Billing is a Core Platform concern.

It must not be coupled directly to restaurant functionality.

Core billing entities will eventually include:

- Invoice
- Payment
- Refund
- Payment provider reference

Payment providers may include:

- Razorpay
- Stripe

Provider-specific implementation must be isolated behind a payment abstraction.

---

# 14. Notification

Notifications are platform-level entities.

They may eventually support:

- in-app notifications
- email
- push notifications
- system alerts

Examples:

- subscription payment failed
- invitation received
- branch created
- security event
- synchronization issue

Notification infrastructure must remain independent of restaurant-specific workflows.

---

# 15. File

The File entity represents metadata for an uploaded object.

Actual file contents should be stored in object storage.

Possible storage:

- S3
- S3-compatible storage

The database should contain metadata such as:

- file id
- organization id
- uploader
- object key
- filename
- content type
- size
- checksum
- created_at

The application should not use PostgreSQL as general-purpose binary file storage.

---

# 16. Audit Log

Audit logs record important system and business events.

Examples:

- user.login
- user.logout
- user.created
- role.created
- role.updated
- permission.changed
- organization.updated
- subscription.changed
- security event

Audit logs should be designed for traceability.

Important audit records should be treated as immutable.

---

# 17. Settings

Settings represent configurable behavior.

Settings should be separated by scope where appropriate.

Possible scopes:

- platform
- organization
- branch
- user

Examples:

Organization settings:

- timezone
- currency
- branding
- business preferences

Branch settings:

- operating hours
- receipt configuration
- POS settings

User settings:

- interface preferences
- notification preferences

---

# 18. Restaurant Module Boundary

Restaurant-specific entities do not belong in the Core Platform.

Restaurant Module examples:

- Menu
- Menu Category
- Menu Item
- Table
- Order
- Order Item
- Kitchen Ticket
- Inventory
- Recipe
- Customer
- Delivery

The dependency direction must be:

Core Platform
        ↑
Restaurant Module

The Core Platform must not depend on Restaurant entities.

---

# 19. Future Business Modules

Future modules may include:

Retail Module
Salon Module
Service Business Module

Each module should consume Core Platform capabilities rather than duplicate them.

Example:

Retail Module
├── uses User
├── uses Organization
├── uses Branch
├── uses Roles
├── uses Permissions
├── uses Subscription
└── implements Retail-specific entities

---

# 20. Entity Ownership

Every entity must have an explicit ownership model.

Examples:

Organization-owned:
- Subscription
- Organization Settings

Branch-owned:
- Orders
- Tables
- Inventory

User-owned:
- Personal preferences

Platform-owned:
- Permission definitions
- System configuration

Ownership determines:

- authorization
- synchronization
- data isolation
- deletion behavior
- reporting scope

---

# 21. Entity IDs

Distributed/offline-capable entities should use globally unique identifiers.

The chosen identifier strategy must allow safe creation while the desktop application is offline.

The implementation should avoid relying on a central auto-increment sequence for synchronizable business entities.

The exact UUID implementation will be finalized during database architecture implementation.

---

# 22. Timestamps

Persisted entities should use timezone-aware timestamps.

Canonical storage convention:

UTC

Application clients convert timestamps into the appropriate display timezone.

Standard fields:

created_at
updated_at

Entities requiring deletion tracking may additionally use:

deleted_at

---

# 23. Deletion Policy

Deletion must be entity-specific.

Soft deletion should be used where recovery, synchronization, auditability, or historical references require it.

Hard deletion may be appropriate for certain non-business or temporary records.

Financial and audit records require special handling and should not be casually deleted.

---

# 24. Offline-First Considerations

Synchronizable entities must be designed with distributed operation in mind.

Relevant metadata may include:

- globally unique id
- organization_id
- branch_id
- created_at
- updated_at
- deleted_at
- version
- synchronization state

The exact synchronization metadata will be finalized during the Offline Sync Architecture stage.

---

# 25. Financial Data Principle

Financial records must not be treated as unrestricted CRUD entities.

Examples:

- payments
- refunds
- invoices
- financial adjustments

Important financial operations should use explicit state transitions and audit trails.

Historical financial information must remain traceable.

---

# 26. Domain Design Rules

The following rules are mandatory:

1. Core Platform must remain business-vertical agnostic.
2. Organization is the primary SaaS tenant.
3. Branch belongs to Organization.
4. User identity is independent of Organization.
5. Membership connects Users to Organizations.
6. Authorization is based on Roles and Permissions.
7. Subscription belongs to Organization.
8. Restaurant entities belong to Restaurant Module.
9. Backend enforces tenant isolation.
10. Synchronizable entities must support offline creation.
11. Financial records require stronger auditability.
12. Domain entities must have explicit ownership.
13. Client-provided organization or branch identifiers are never sufficient authorization proof.
14. Business-critical historical records must not be casually hard-deleted.
15. Platform modules must not depend on Restaurant-specific concepts.

---

# 27. Target Relationship Model

The high-level relationship is:

User
│
├── Membership ── Organization
│                    │
│                    ├── Branch
│                    ├── Subscription
│                    ├── Settings
│                    ├── Files
│                    └── Business Data
│
└── User Preferences

Membership
│
└── Role
       │
       └── Permission

Subscription
│
└── SubscriptionPlan