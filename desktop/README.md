# Architecture overview

                    QUANTUM BUSINESS OS
                           │
            ┌──────────────┴──────────────┐
            │                             │
      CORE PLATFORM                 BUSINESS MODULES
            │                             │
   ┌────────┼─────────┐          ┌────────┼─────────┐
   │        │         │          │        │         │
Identity  Tenant    Billing    Restaurant  Retail  Salon
   │        │         │           │
Users   Organization Subscription │
Roles   Branch       Payments     │
Permissions         Plans         │
Audit   Settings    Notifications │
Files                             │
                                  │
                         POS / Menu / Orders
                         Tables / Kitchen
                         Inventory / CRM

# Phase 1 folder structure

Quantum-Business-OS/
│
├── .vscode/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── database.py
│   │   │   └── dependencies.py
│   │   │
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── ...
│   │   │
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── organizations/
│   │   │   ├── branches/
│   │   │   ├── users/
│   │   │   ├── roles/
│   │   │   ├── permissions/
│   │   │   ├── subscriptions/
│   │   │   ├── billing/
│   │   │   ├── notifications/
│   │   │   ├── files/
│   │   │   ├── audit/
│   │   │   └── settings/
│   │   │
│   │   └── shared/
│   │       ├── models/
│   │       ├── schemas/
│   │       ├── exceptions/
│   │       └── utils/
│   │
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── ...
│
├── desktop/
│   ├── electron/
│   │   ├── main.ts
│   │   └── preload.ts
│   │
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── services/
│   │   ├── stores/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── types/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   │
│   └── ...
│
├── shared/
│   ├── contracts/
│   └── types/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── database/
│   └── decisions/
│
├── deployment/
│
└── scripts/

# Core entities

User
 │
 ├── Organization Membership
 │          │
 │          ├── Organization
 │          │       │
 │          │       ├── Branch
 │          │       └── Subscription
 │          │
 │          └── Role
 │                  │
 │                  └── Permissions

Primary entities

 | Entity            | Purpose                                 |
| ----------------- | --------------------------------------- |
| User              | Human account                           |
| Organization      | Business/company tenant                 |
| Branch            | Physical/business location              |
| Membership        | User's relationship with organization   |
| Role              | Collection of permissions               |
| Permission        | Specific capability                     |
| Subscription      | Organization's current plan             |
| Subscription Plan | Starter/Standard/Premium/Enterprise     |
| Invoice           | Billing record                          |
| Payment           | Payment transaction                     |
| Notification      | System/user notification                |
| File              | Object-storage metadata                 |
| Audit Log         | Security/business activity history      |
| Setting           | Configurable platform/business settings |

# Authentication architecture

Desktop
   │
   │ HTTPS
   ▼
FastAPI
   │
   ├── Authentication
   ├── Authorization
   └── PostgreSQL

# Organization + branch architecture
Tenant architecture

Organization
│
├── Branch 1
│
├── Branch 2
│
└── Branch 3 

Small restuarnt simply has

Organization
└── Branch

# this matters because Organization
Some data belongs to the organization:

├── Subscription
├── Branding
├── Billing
└── Organization settings

Some data belongs to a branch:

Branch
├── Orders
├── Tables
├── Inventory
├── Staff assignments
└── Branch settings

# Roles + permissions architecture

user
 ↓
membership
 ↓
role
 ↓
permissions

## Example
Role: Manager

Permissions:
- orders.view
- orders.create
- orders.cancel
- inventory.view
- inventory.edit
- reports.view

# Subscription architecture

Starter
₹999/month

Standard
₹2,499/month

Premium
₹4,999/month

Enterprise
Custom  

# Local database + cloud database architecture

             CLOUD
          PostgreSQL
              ▲
              │
          Sync Engine
              │
              ▼
Desktop ── SQLite

# Offline sync architecture

                 CLOUD
              PostgreSQL
                  ▲
                  │
            Sync API / Engine
                  │
             Internet
                  │
                  ▼
             Desktop App
                  │
            ┌─────┴─────┐
            │           │
         SQLite      Sync Queue
            │           │
            └─────┬─────┘
                  │
              POS writes