# Architecture

Guidelines for directory structure, function extraction, and presenter pattern.

---

## 🔥 CRITICAL: Colocation First

**THE GOLDEN RULE: Everything lives next to what uses it.**

- ❌ **NEVER** create centralized directories: `utils/`, `helpers/`, `api/`, `services/`, `lib/`, `hooks/`
- ✅ **ALWAYS** place code next to the component that uses it
- 🎯 **If a function is used by `ComponentA`, it must live in `ComponentA/` directory**
- 🎯 **If data fetching is needed by a page, `queries.ts` must live in that page directory**

**When in doubt: Collocate. When certain: Still collocate.**

---

## Directory Structure

### Component Collocation

**COLLOCATE EVERYTHING. NO EXCEPTIONS.**

All page-related code lives in the page directory: components, data fetching, logic functions, and types. Everything is collocated with the page. **If you're thinking of creating a shared directory, stop. Collocate first, refactor later when you have 3+ identical copies.**

```
pages/
  gradient-map/                  # URL: /gradient-map (kebab-case)
    page.tsx                     # Page component (always page.tsx)
    queries.ts                   # Data fetching functions
    calculateDistance.ts         # Logic function
    createGeoJSON.ts             # Logic function
    types.ts                     # Type definitions
    components/
      gradient-layer/
        index.tsx                # Child component (export const GradientLayer)
        queries.ts               # Child's data fetching
        gradientLogic.ts         # Child's logic
        components/
          color-scale/
            index.tsx            # Grandchild (export const ColorScale)
      route-markers/
        index.tsx                # Child (export const RouteMarkers)
        queries.ts               # Child's data fetching
```

**Key Principles**:
- 🔥 **COLLOCATE EVERYTHING** - Code lives next to what uses it
- Data fetching functions are **collocated** in the same directory as the component that uses them
- Logic functions are **collocated** at the same level as the component that uses them
- Page directory contains everything: page component, queries, logic, types, and child components
- Child components live in `components/` subdirectory under their parent
- Each component (page or child) can have its own data fetching and logic files
- Grandchildren follow the same pattern under their parent's `components/` directory
- ❌ **NEVER create centralized directories**: `utils/`, `helpers/`, `api/`, `services/`, `lib/`, `hooks/`, `common/`, `shared/`

### Naming Conventions

> **Note**: The `unicorn/filename-case` lint rule only allows `kebab-case` or `camelCase` filenames. `PascalCase` filenames and directory names will cause lint errors.

**Directories:**
- Page directories: `kebab-case` (e.g., `gradient-map/`, `user-profile/`)
- Component directories: `kebab-case` (e.g., `gradient-layer/`, `color-scale/`)
- Special directories: `components/`

**Files:**
- Page: `route.tsx`
- Component: `kebab-case` directory with `index.tsx` (e.g., `gradient-layer/index.tsx`)
- Logic functions: `camelCase.ts` (e.g., `validateEmail.ts`, `calculateDistance.ts`)
- Data fetching: `queries.ts`
- Types: `types.ts`

**Exports:**
- Component exports remain `PascalCase` (e.g., `export const GradientLayer = ...`)

### Parent-Child Hierarchy

Place child components in a `components/` subdirectory under their parent. Grandchildren follow the same pattern.

```
user-profile/                    # URL: /user-profile
  page.tsx                       # Parent (page)
  queries.ts                     # Page's data fetching
  parentLogic.ts
  components/
    profile-card/
      index.tsx                  # Child (export const ProfileCard)
      queries.ts                 # Child's data fetching
      childLogic.ts
      components/
        status-badge/
          index.tsx              # Grandchild (export const StatusBadge)
          grandchildLogic.ts
```

---

## Data Fetching

**NO CENTRALIZED API LAYER. COLLOCATE YOUR QUERIES.**

Place data fetching functions in a `queries.ts` file at the same level as the component that uses them. Each page and component has its own `queries.ts`. Never create a global `api/` or `services/` directory.

```typescript
// pages/user-profile/queries.ts
import { z } from 'zod'

const userSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email(),
})

export type User = z.infer<typeof userSchema>

export async function fetchUser(userId: string): Promise<User> {
  const response = await fetch(`/api/users/${userId}`)
  if (!response.ok) throw new Error('Failed to fetch user')

  const json = await response.json()
  return userSchema.parse(json)  // Validate with zod
}

export async function fetchUserPosts(userId: string): Promise<Post[]> {
  const response = await fetch(`/api/users/${userId}/posts`)
  if (!response.ok) throw new Error('Failed to fetch posts')

  const json = await response.json()
  return postArraySchema.parse(json)
}
```

```typescript
// pages/user-profile/page.tsx
import { fetchUser, fetchUserPosts } from './queries'

export default async function UserProfilePage({ params }: { params: { id: string } }) {
  const user = await fetchUser(params.id)
  const posts = await fetchUserPosts(params.id)
  return <UserProfile user={user} posts={posts} />
}
```

**Key Points**:
- Data fetching functions go in `queries.ts` file
- Use zod schemas for type safety and runtime validation within the same file
- Each component (page or child) can have its own `queries.ts` file
- Group related queries together in one file

---

## Function Extraction

**COLLOCATE FUNCTIONS. ALWAYS.**

Make functions controllable via arguments. Don't depend on global state or closures. **And most importantly: Place function files at the same level as the component that uses them. No exceptions.**

```typescript
// ❌ Depends on global state
function validateUser() {
  const user = getCurrentUser()  // Global state
  if (!user.email) return false
  return true
}

// ✅ Controlled via arguments
function validateUser(user: User): boolean {
  if (!user.email) return false
  return true
}
```

Place function files at the same level as the component that uses them.

```typescript
// pages/user-profile/validateEmail.ts
export function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

// Use in pages/user-profile/page.tsx
import { validateEmail } from './validateEmail'
```

For child component logic:

```typescript
// pages/user-profile/components/EmailInput/validateFormat.ts
export function validateFormat(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

// Use in pages/user-profile/components/EmailInput/EmailInput.tsx
import { validateFormat } from './validateFormat'
```

---

## Presenter Pattern

Consolidate conditional text in presenter.ts. Don't embed in JSX.

```typescript
// presenter.ts
export function getUserStatusText(status: string): string {
  switch (status) {
    case "active": return "Active"
    case "inactive": return "Inactive"
    case "pending": return "Pending"
    default: return "Unknown"
  }
}

export function getUserStatusColor(status: string): string {
  switch (status) {
    case "active": return "green"
    case "inactive": return "gray"
    case "pending": return "yellow"
    default: return "gray"
  }
}

// Use in component
import { getUserStatusText, getUserStatusColor } from './presenter'

function UserStatus({ status }: { status: string }) {
  return (
    <Badge color={getUserStatusColor(status)}>
      {getUserStatusText(status)}
    </Badge>
  )
}
```

---

## 🚫 Anti-Patterns (NEVER DO THIS)

### ❌ FORBIDDEN: Creating Centralized Directories

**DO NOT** create separate directories for utility functions, helpers, or any shared code. This is a violation of the colocation principle. Place function files at the same level as the components that use them.

**Banned directory names**: `utils/`, `helpers/`, `api/`, `services/`, `lib/`, `hooks/`, `common/`, `shared/`

```
❌ Bad: Centralized utils
pages/
  user-profile/
    page.tsx
utils/
  validateEmail.ts
  formatDate.ts

✅ Good: Collocated functions
pages/
  user-profile/
    page.tsx
    validateEmail.ts
    formatDate.ts
```

### Separating Data Fetching into Global Directories

Don't create centralized `api/` or `services/` directories. Keep data fetching functions in `queries.ts` files with the components that use them.

```
❌ Bad: Centralized API layer
pages/
  user-profile/
    page.tsx
api/
  fetchUser.ts
  fetchPosts.ts

✅ Good: Collocated data fetching
pages/
  user-profile/
    page.tsx
    queries.ts     # fetchUser, fetchUserPosts
```
