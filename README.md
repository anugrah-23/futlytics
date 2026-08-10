# Football Analytics Platform

Top-5 European league analytics — Playerprint-style player percentile profiles
**plus** a team/tactical dashboard. Streamlit app fed by a weekly `soccerdata`
ETL (FBref + WhoScored), stored as Parquet.

See `football-analytics-PRD.md`, `-design-doc.md`, `-technical-spec.md` for the
full plan.

## Setup

```bash
python -m venv .venv
# Windows (Git Bash): source .venv/Scripts/activate
# macOS/Linux:        source .venv/bin/activate
pip install -r requirements.txt
```

## Phase 0 — ETL proof of concept

Pull one league/season (Premier League 2024/25) end to end and verify the
`soccerdata` pull + per-90/percentile transforms:

```bash
python -m etl.poc_pull          # inspect only
python -m etl.poc_pull --write  # also persist a sample to data/processed/
```

## Run the app

```bash
streamlit run app/Home.py
```

## Layout

```
app/            Streamlit multi-page app (Home = League Overview)
  pages/        Player Profile, Team Dashboard, Compare
etl/            fetch (fbref/whoscored) → transform → run_all orchestration
viz/            shared radar (plotly) + pitch (mplsoccer) builders
data/
  raw/          soccerdata cache + raw pulls  (gitignored)
  processed/    app-facing Parquet            (committed, weekly refresh)
  tmp/          atomic-write staging          (gitignored)
data_access.py  cached loader layer the app reads through
tests/          unit tests for the percentile / per-90 logic
```

## Data & ethics

Unofficial FBref/WhoScored scraping for **personal, non-commercial** use only;
no redistribution of raw scraped data. Sources can change markup and break the
scraper — the pipeline serves last-good data rather than crashing.
