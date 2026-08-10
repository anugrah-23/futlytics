# Football Analytics Platform — Technical Specification

Read alongside the PRD (what to build) and the Design Doc (how it looks). This document
covers how it's built, and is the primary reference for implementation.

## 1. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| App framework | Streamlit (multi-page app) |
| Data acquisition | `soccerdata` (wraps WhoScored + FBref scraping) |
| Data processing | pandas |
| Visualization | mplsoccer (pitch plots), plotly (radars, interactive charts) |
| Storage | Parquet files under `data/` (via pandas + pyarrow) |
| Scheduling | GitHub Actions cron job, runs ETL weekly |
| Hosting | Streamlit Community Cloud, deployed from GitHub |

Parquet over a hosted database: no server process to run or pay for, plays well with Streamlit
Community Cloud's free tier, and is trivially version-controlled and diffable in git.

## 2. Architecture

```
Data sources (WhoScored: Opta events, FBref: aggregated stats)
        │  soccerdata
        ▼
Python ETL pipeline  (fetch → clean → compute per-90 & percentiles)
        │
        ▼
Data store  (Parquet files, refreshed weekly by GitHub Actions)
        │
        ▼
Streamlit app  (Player Profile, League Overview, Team Dashboard, Compare)
        │
        ▼
Streamlit Community Cloud  (auto-deploys on git push)
```

## 3. Data model

### `players`
`player_id, name, team_id, league, position, age, nationality, minutes_played`

### `teams`
`team_id, name, league, season`

### `matches`
`match_id, date, home_team_id, away_team_id, competition, season`

### `player_season_stats`
`player_id, season, stat_name, value, percentile`
(percentile computed against positional peers within the selected league + season)

### `match_events`
`event_id, match_id, team_id, player_id, event_type, x, y, end_x, end_y, outcome, minute`
(event_type: pass / shot / tackle / carry / duel / etc. — this table is what powers the team
tactical dashboard: pass networks, heatmaps, pressing, shot maps)

## 4. ETL pipeline

- `etl/fetch_fbref.py` — pulls player/team season stats via `soccerdata.FBref`, per
  league/season
- `etl/fetch_whoscored.py` — pulls match event data via `soccerdata.WhoScored`. This scraper is
  Selenium-based, so the runner (local machine or GitHub Actions) needs a headless Chrome/
  Chromium available
- `etl/transform.py` — cleans raw output, computes per-90 normalized stats, computes
  percentiles per position group within each league/season
- `etl/run_all.py` — orchestrates fetch → transform → write, and is the single entrypoint the
  scheduler calls

**Error handling:** each fetch step runs in its own try/except; a failure logs and aborts that
step without touching previously-written good data. Write new output to a temp path and swap
it into place only on success, so a partial or failed run never leaves `data/` in a broken
state.

**Rate limiting / etiquette:** deliberate delays between requests; rely on `soccerdata`'s local
caching of raw pages so unchanged data isn't re-fetched.

**Legal/ethical note:** WhoScored and FBref scraping here is unofficial and for personal,
non-commercial use only. No redistribution of raw scraped data. This is standard practice
across the hobbyist football-analytics community, but it's worth stating explicitly since the
scrapers can also stop working without notice if a source site changes its markup —design the
pipeline to degrade gracefully (serve last-good data) rather than crash the app.

## 5. Scheduling & automation

A GitHub Actions workflow on a weekly cron trigger runs `etl/run_all.py` and commits the
refreshed `data/*.parquet` files back to the repository. Streamlit Community Cloud watches the
repo and redeploys automatically on push, so a successful weekly run is enough to update the
live app with no manual step.

## 6. App architecture

```
app/
├── Home.py                     # league overview / landing page
└── pages/
    ├── 1_Player_Profile.py
    ├── 2_Team_Dashboard.py
    └── 3_Compare.py
viz/
├── radar.py                    # shared percentile radar/pizza chart builders
└── pitch.py                    # shared mplsoccer pitch-plot builders
data_access.py                  # thin loader layer, wraps st.cache_data around Parquet reads
```

- Pages never read Parquet files directly — they call `data_access.py`, which owns caching
  (`st.cache_data`) so repeated navigation doesn't re-read from disk every time.
- Filter state (league, season, position) lives in `st.session_state` so it persists as the
  user moves between pages.

## 7. Non-functional requirements

- **Performance:** after the cache warms, page loads should stay under ~2 seconds.
- **Resilience:** the app must run correctly even if the latest weekly refresh partially
  failed — it always serves the last-known-good dataset, never a half-written one.
- **Respectful scraping:** rate-limited requests, no redistribution of raw source data,
  personal/non-commercial use only.

## 8. Testing

- Unit tests for the percentile-computation and per-90-normalization logic (these are the
  numbers the whole product's credibility rests on)
- A smoke test that runs the ETL pipeline end to end on a small sample (one team, one match)
  and confirms it completes without error
- A short manual QA pass on each page before every deploy

## 9. Deployment steps

1. Push the repository to GitHub
2. Connect the repo in Streamlit Community Cloud, entrypoint `app/Home.py`
3. No secrets required for v1 (no paid APIs in scope)
4. Confirm the GitHub Actions workflow has permission to commit updated data files back to the
   repo

## 10. Build phases (engineering checklist)

| Phase | Tasks |
|---|---|
| 0 | Repo scaffold; `soccerdata` proof-of-concept pull for one league/season |
| 1 | Data model + transform/percentile logic; Player Profile page |
| 2 | League Overview page |
| 3 | Team Dashboard: pass network, heatmap, pressing, defensive shape, shot map |
| 4 | Compare page |
| 5 | GitHub Actions weekly-refresh workflow; deploy to Streamlit Community Cloud |

## 11. Open risks

- WhoScored scraping is Selenium-based and the most fragile part of the pipeline — likely to
  need occasional maintenance, and a fallback source (e.g. Sofascore or FotMob) is worth
  keeping in mind if it breaks for an extended period
- Free-tier limits on both Streamlit Community Cloud (compute/memory) and GitHub Actions
  (monthly minutes) should be watched as data volume grows across five leagues and event-level
  match data
