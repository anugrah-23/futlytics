"""Player DNA registry: the 12 concepts, their parameters, and the 11-category
fingerprint — the single source of truth the DNA builder and Profile UI share.

Two layers, mirroring the PlayerPrint reference:
  * CONCEPTS  — 13 detailed parameter groups (Passing Profile, Progression, …).
                Each Param maps to a column the builder computes per player-season.
  * CATEGORIES — 11 high-level DNA axes (Progression, Carrying, Passing, …) shown
                as the overview radar; each is the mean percentile of a curated
                set of parameter keys (which may span concepts).

Every value here is derived from WhoScored/Opta events (etl.dna_events); FBref's
advanced tables are blank at source, so this is featured-club-only.

unit:   per90 -> builder already normalised to per-90 (shown "/90")
        %     -> a rate/share (shown with %)
        ratio -> a unitless ratio
invert=True: lower raw is better, so the percentile is flipped ("more filled = better").
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Param:
    key: str          # column name the builder produces
    label: str
    concept: str
    unit: str = "per90"
    invert: bool = False


# --- 13 concepts x their parameters ----------------------------------------
# (12 from the reference + an explicit "Progression" group; "Half-Spaces" and
#  "Final Third" both live under the Final-Third-Actions category.)
PARAMS: list[Param] = [
    # Passing Profile
    Param("pass_vol", "Passes", "Passing Profile"),
    Param("pass_pct", "Pass completion", "Passing Profile", "%"),
    Param("long_pct", "Long-ball accuracy", "Passing Profile", "%"),
    Param("fwd_pass_pct", "Forward-pass share", "Passing Profile", "%"),
    Param("through_balls", "Through balls", "Passing Profile"),
    Param("switches", "Switches of play", "Passing Profile"),

    # Progression
    Param("prog_passes", "Progressive passes", "Progression"),
    Param("prog_pass_dist", "Progressive pass distance", "Progression"),
    Param("passes_final_third", "Passes into final third", "Progression"),
    Param("prog_carries", "Progressive carries", "Progression"),
    Param("carries_final_third", "Carries into final third", "Progression"),

    # Carrying Profile
    Param("carries", "Carries", "Carrying Profile"),
    Param("carry_dist", "Carry distance", "Carrying Profile"),
    Param("take_ons", "Take-ons attempted", "Carrying Profile"),
    Param("take_on_pct", "Take-on success", "Carrying Profile", "%"),
    Param("carries_box", "Carries into box", "Carrying Profile"),

    # Shooting & Footedness
    Param("shots", "Shots", "Shooting & Footedness"),
    Param("goals", "Goals", "Shooting & Footedness"),
    Param("sot_pct", "Shots on target", "Shooting & Footedness", "%"),
    Param("foot_right_pct", "Right-foot share", "Shooting & Footedness", "%"),
    Param("foot_left_pct", "Left-foot share", "Shooting & Footedness", "%"),
    Param("foot_head_pct", "Header share", "Shooting & Footedness", "%"),
    Param("two_footed", "Weaker-foot balance", "Shooting & Footedness", "%"),

    # Aerial Duels
    Param("aerials", "Aerial duels", "Aerial Duels"),
    Param("aerials_won", "Aerials won", "Aerial Duels"),
    Param("aerial_pct", "Aerial win", "Aerial Duels", "%"),
    Param("off_aerials", "Offensive aerials", "Aerial Duels"),
    Param("def_aerials", "Defensive aerials", "Aerial Duels"),

    # Hold-Up Play
    Param("att_touches", "Att-third touches", "Hold-Up Play"),
    Param("fouls_won", "Fouls won", "Hold-Up Play"),
    Param("dispossessed", "Dispossessed", "Hold-Up Play", "per90", invert=True),
    Param("retention_pct", "Possession retention", "Hold-Up Play", "%"),
    Param("ft_pass_pct", "Final-third pass completion", "Hold-Up Play", "%"),

    # Decision Making
    Param("turnovers", "Turnovers", "Decision Making", "per90", invert=True),
    Param("pass_success_dm", "Pass success", "Decision Making", "%"),
    Param("take_on_success_dm", "Take-on success", "Decision Making", "%"),
    Param("shot_conv", "Shot conversion", "Decision Making", "%"),

    # Final Third
    Param("ft_touches", "Final-third touches", "Final Third"),
    Param("ft_passes", "Final-third passes", "Final Third"),
    Param("passes_box", "Passes into box", "Final Third"),
    Param("key_passes", "Key passes", "Final Third"),

    # Half-Spaces
    Param("hs_touches", "Half-space touches", "Half-Spaces"),
    Param("hs_passes", "Half-space passes", "Half-Spaces"),
    Param("hs_receptions", "Half-space receptions", "Half-Spaces"),
    Param("hs_left_pct", "Left half-space share", "Half-Spaces", "%"),
    Param("hs_right_pct", "Right half-space share", "Half-Spaces", "%"),

    # Tempo Control
    Param("touches", "Touches", "Tempo Control"),
    Param("pass_per_touch", "Passes per touch", "Tempo Control", "ratio"),
    Param("one_touch_pct", "One-touch passes", "Tempo Control", "%"),
    Param("short_share", "Short-pass share", "Tempo Control", "%"),

    # Defending Profile
    Param("tackles", "Tackles", "Defending Profile"),
    Param("tackle_pct", "Tackle win", "Defending Profile", "%"),
    Param("interceptions", "Interceptions", "Defending Profile"),
    Param("clearances", "Clearances", "Defending Profile"),
    Param("blocks", "Blocks", "Defending Profile"),

    # Post-Recovery
    Param("recoveries", "Ball recoveries", "Post-Recovery"),
    Param("high_recoveries", "Att-half recoveries", "Post-Recovery"),
    Param("post_rec_ret", "Post-recovery retention", "Post-Recovery", "%"),
    Param("counterpress", "Att-third recoveries", "Post-Recovery"),

    # Link-Up & Synergy
    Param("received", "Passes received", "Link-Up & Synergy"),
    Param("prog_received", "Progressive receptions", "Link-Up & Synergy"),
    Param("partners", "Distinct pass partners", "Link-Up & Synergy", "ratio"),
    Param("pass_share", "Team pass share", "Link-Up & Synergy", "%"),
]

# Concept display order (drives the Profile page sections).
CONCEPTS: list[str] = [
    "Passing Profile", "Progression", "Carrying Profile", "Shooting & Footedness",
    "Aerial Duels", "Hold-Up Play", "Decision Making", "Final Third",
    "Half-Spaces", "Tempo Control", "Defending Profile", "Post-Recovery",
    "Link-Up & Synergy",
]

# 11 DNA fingerprint categories -> the parameter keys that define each axis.
# A category score is the mean percentile of these keys (invert already applied).
CATEGORIES: dict[str, list[str]] = {
    "Progression": ["prog_passes", "prog_carries", "passes_final_third",
                    "prog_pass_dist", "carries_final_third"],
    "Carrying": ["carries", "carry_dist", "take_ons", "take_on_pct", "carries_box"],
    "Passing": ["pass_vol", "pass_pct", "long_pct", "through_balls", "switches"],
    "Shooting": ["shots", "goals", "sot_pct", "shot_conv"],
    "Aerial": ["aerials", "aerials_won", "aerial_pct", "off_aerials", "def_aerials"],
    "Hold-Up": ["att_touches", "fouls_won", "dispossessed", "retention_pct"],
    "Tempo": ["touches", "pass_per_touch", "one_touch_pct", "short_share"],
    "Defending": ["tackles", "tackle_pct", "interceptions", "clearances", "blocks"],
    "Recovery": ["recoveries", "high_recoveries", "post_rec_ret", "counterpress"],
    "Decision": ["turnovers", "pass_success_dm", "take_on_success_dm", "shot_conv"],
    "Final Third Actions": ["ft_touches", "ft_passes", "passes_box", "key_passes",
                            "hs_receptions"],
}

PARAM_BY_KEY = {p.key: p for p in PARAMS}
CONCEPT_PARAMS: dict[str, list[Param]] = {
    c: [p for p in PARAMS if p.concept == c] for c in CONCEPTS
}
