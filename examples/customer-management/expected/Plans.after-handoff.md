# customer-backoffice Plans.md

作成日: 2026-01-01

---

## Phase 1: Existing auth work

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 1.1  | Login page | test passes | - | cc:完了 [abc1234] |
| 1.2  | Logout | test passes | 1.1 | cc:TODO |

User note: keep this line.

<!-- spec2ship:begin run=s2s-20261110-141130-badcfd plan=557bcfaaa547 -->
## Phase 2: Customer data and API (Spec2Ship)

Purpose: Backend, API and database support for search and create

Spec: `.spec2ship/planning/spec.md` (approved Spec2Ship sub-spec; requirement IDs trace to it)

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 2.1 | Add unique index on customers.phone and name search index (Prisma migration) [REQ-CUS-001, REQ-CUS-002] files: prisma/schema.prisma [tdd:required] | prisma migrate dev applies cleanly; unique constraint rejects duplicate phone in a test | - | cc:完了 [1234567] |
| 2.2 | GET /api/customers?q=&page= case-insensitive partial name / exact phone search, 20 per page [REQ-CUS-001] files: src/routes/customers.js [tdd:required] | jest tests for name/phone/pagination pass | 2.1 | cc:完了 [1234567] |
| 2.3 | POST /api/customers manager-only create with duplicate phone error [REQ-CUS-002] files: src/routes/customers.js [tdd:required] [feature:security] | jest tests: 201 on valid input, 409 'Phone number already registered', 403 for sales staff | 2.1 | cc:完了 [1234567] |

## Phase 3: Customer screens (Spec2Ship)

Spec: `.spec2ship/planning/spec.md` (approved Spec2Ship sub-spec; requirement IDs trace to it)

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 3.1 | Customer list screen with search and pagination per Figma 12:345 [REQ-CUS-001] [feature:a11y] | component tests for search input, empty and loading states pass | 2.2 | cc:完了 [1234567] |
| 3.2 | Create customer form per Figma 12:400 \| shows API errors [REQ-CUS-002] [feature:a11y] | form test shows 'Phone number already registered' on 409 | 2.3 | cc:完了 [1234567] |
| 3.3 | Customer detail screen per Figma 12:450 [REQ-CUS-003] | detail renders name, phone, email, created date in a component test | 2.2 | cc:完了 [1234567] |

<!-- spec2ship:end run=s2s-20261110-141130-badcfd -->
