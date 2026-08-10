# Football Analytics Platform — Design Doc

Covers UX/UI direction: how the product looks, feels, and is navigated. Read alongside the PRD
(what to build) and the Technical Spec (how it's built).

## 1. Design principles

- **Data-dense but scannable.** Percentile visuals are the primary language, not raw tables —
  raw numbers support the visuals, they don't replace them.
- **One consistent visual grammar** across player and team pages: the same percentile-color
  logic, the same pitch styling, the same typography scale everywhere.
- **Fast to reach anything.** Any player or team should be reachable in two clicks or fewer
  from any page.
- **Its own identity.** The interaction pattern (percentile radars/pizzas) is deliberately
  similar to Playerprint's — that's the part being emulated — but the color palette,
  typography, and the team/tactical section should read as a distinct product, not a clone.

## 2. Information architecture

- Top-level navigation: **League Overview** / **Player Profile** / **Team Dashboard** / **Compare**
- A persistent filter bar (league, season, position) whose state carries across pages via
  Streamlit session state, so switching pages doesn't reset context

## 3. Page-by-page design

### 3.1 League overview
- Sidebar: league/season filters
- Main area: standings table, with two or three leaderboard widgets in a grid below it
- Sortable columns on every table
- Clicking a team or player row navigates to that entity's dedicated page

### 3.2 Player profile
- Header band: name, team badge, position, age, nationality
- Body: one section per stat "concept" (passing, carrying, shooting & footedness, aerial
  duels, defending, decision-making, final third, etc.), each with:
  - a percentile radar or pizza chart, slices colored by percentile intensity
  - a compact per-90 stat table underneath the chart
- Season/competition toggle pinned near the header, not buried in a sidebar
- A visible "limited sample" badge on players below the minutes-played threshold, with the
  percentile chart either grayed out or replaced by a plain stat table

### 3.3 Team dashboard
- Header: team name, badge, current league position
- Sub-navigation (tabs or stacked sections): Pass Network | Territory & Heatmap | Pressing |
  Defensive Shape | Shot Map
- All pitch visuals share one consistent pitch style (orientation, line color, background)
  so a user's eye doesn't have to re-orient between sections
- Where the charting library supports it (Plotly), hover tooltips expose exact values without
  cluttering the base visual

### 3.4 Compare
- Two columns side by side (three if the viewport allows)
- One overlaid radar per shared concept, plus a simple stat-difference table below it

## 4. Visual style

- Base palette: a pitch-inspired neutral (deep green or charcoal) background with a single
  accent hue used consistently for "high percentile" — avoid rainbow-coding across pages
- Typography: one clean sans-serif family, a small consistent size scale (page title / section
  header / body / chart label); Streamlit's defaults are a fine starting point, lightly themed
  via `.streamlit/config.toml` rather than custom CSS everywhere
- Charts: consistent legend and axis styling across every chart type; the percentile scale is
  explained once, visibly, near the first chart a user encounters

## 5. Edge cases & states

- **Low minutes played** — badge + degrade the percentile chart rather than show a misleading
  100th-percentile spike from a three-appearance sample
- **Goalkeepers** — a separate metric set (shot-stopping, distribution, claims) rather than
  forcing them through outfield categories like carrying or dribbling
- **Failed or stale data refresh** — show a small "data last updated <date>" note; the app
  keeps serving the last good dataset rather than failing to load
- **No search results / empty state** — a plain, clear empty-state message, never a blank page

## 6. Responsiveness

Streamlit's default responsive behavior is acceptable for v1. This is a data-dense analytics
tool, so design for desktop/laptop first and let it degrade gracefully on tablet; a dedicated
mobile layout is not a v1 goal.

## 7. Accessibility

- Percentile scales pair color with a visible numeric label — never color alone
- Sufficient contrast between chart fill and background in both the default and any dark theme
