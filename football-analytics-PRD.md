# Football Analytics Platform — Product Requirements Document

## 1. Overview

A web-based football data analytics app covering the Top 5 European leagues. Inspired by
Playerprint (playerprint.streamlit.app), which delivers deep individual player profiles built
from percentile rankings across hundreds of metrics. This project matches that core player
experience and adds a **team/tactical analytics layer** — pass networks, pressing maps,
defensive shape, territory — that player-only tools like Playerprint don't cover.

Personal passion project, built and maintained solo, self-deployed.

## 2. Problem & motivation

Individual-player scouting tools (Playerprint and similar) are excellent for "how good is this
player at X, relative to peers" but stop at the player level. There's a gap for someone who
wants both player-level scouting detail *and* team-level tactical patterns in one place,
without switching between five different paid tools.

## 3. Target audience

- The builder, as a portfolio-quality personal project
- Football analytics enthusiasts and hobbyist scouts who want a free, browsable tool
- Anyone reviewing the project (recruiters, fellow students) as a demonstration of data
  engineering + product + visualization skill

## 4. Goals

- Deliver a player-profile experience on par with Playerprint's core value: percentile-based
  scouting views across passing, carrying, shooting, defending, aerial duels, etc.
- Add genuinely useful team/tactical analytics — the project's differentiator
- Ship a real, deployed, working product with a public URL — not a notebook or a demo video
- Keep data current via an automated weekly refresh, not manual re-exports

## 5. Non-goals (v1)

- Live / real-time in-match data
- User accounts, saved shortlists, personalization
- Monetization or paid tiers
- Betting odds, market-value or transfer prediction models
- Coverage beyond the Top 5 European leagues
- A native mobile app (responsive web only)

## 6. Scope: leagues & seasons

Top 5 European leagues — Premier League, La Liga, Serie A, Bundesliga, Ligue 1 — current
season plus at least one prior season for trend context, matching Playerprint's coverage.

## 7. Features (functional requirements)

### 7.1 League overview (MVP)
- League + season selector
- Standings table
- Leaderboards: top scorers, assists, xG, and a couple of underlying metrics
- Clicking a team or player row jumps to its dedicated page

### 7.2 Player profile (MVP — Playerprint-equivalent)
- Player search / select
- Header: name, team, position, age, nationality
- Percentile radar/pizza charts grouped by concept (passing, carrying, shooting & footedness,
  aerial duels, defending, decision-making, final third, etc.), computed against positional
  peers within the selected league(s) and season
- Underlying per-90 stat table beneath each concept chart
- Season / competition toggle
- Low-minutes players flagged rather than silently shown with unreliable percentiles

### 7.3 Team / tactical dashboard (MVP — the differentiator)
- Team selector
- Pass network: average player positions, pass volume and direction between teammates
- Territory / heatmap of team actions across the pitch
- Pressing intensity map
- Defensive shape / average defensive line height over a match or season sample
- Shot map: shots for and against, with xG

### 7.4 Compare (phase 2)
- 2–3 players, or 2 teams, side by side
- Overlaid percentile radar for shared metrics + a stat-difference table

### 7.5 Filters
League, season, position, and a minimum-minutes-played threshold to exclude small-sample
players from percentile comparisons.

## 8. Data freshness

Scheduled weekly refresh via an automated script. Not real-time — the app always serves the
last successfully refreshed dataset.

## 9. Success criteria

- End-to-end working app at a public URL, no manual steps to view it
- Player profile page functionally matches Playerprint's core scouting-report value
- Team dashboard ships at least three tactical visualizations not present in Playerprint
- Weekly refresh runs unattended and the app never breaks from a failed refresh

## 10. Assumptions & constraints

- Underlying data comes from unofficial scraping of WhoScored (Opta-sourced match events) and
  FBref (aggregated player/team stats) — see the technical spec for detail and risk notes.
  Both sources can change layout and break the scraper; the pipeline must fail gracefully and
  keep serving the last good data rather than showing a broken page.
- Single maintainer, so automation is preferred over manual data wrangling wherever possible.
- Hosting on Streamlit Community Cloud's free tier — the build must respect its resource
  limits (no heavy always-on background jobs inside the app itself).

## 11. Phased roadmap

| Phase | Deliverable |
|---|---|
| 0 | ETL proof of concept — pull one league/season end to end, verify data quality |
| 1 | Data model + percentile computation + Player Profile page |
| 2 | League Overview page |
| 3 | Team / Tactical Dashboard (the differentiator) |
| 4 | Compare page |
| 5 | Weekly-refresh automation + deploy to Streamlit Community Cloud |
