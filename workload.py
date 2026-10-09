import polars as pl

from ulae_common import (Config, artifact, banner, done, fold_text,
                         stage_parser)

DICT_ = [
    "przypisane",       # assigned
    "ponownie otwarte",  # reopened
    "otwarte",          # opened
    "zamknięte",        # closed
    "oflagowany",       # flagged
    "dostosowane",      # reserve adjusted
    "zatwierdzone",     # approved
    "płatność",         # payment
    "dochodzenie",      # litigation
]

REAL_ADJUSTER_ = "przypisane"

INPUT_COLUMNS_ = ["CLAIMID", "ADJUSTER", "EVENTTIMESTAMP", "HISTORYTYPE",
                  "CZY_RZECZOWA", "CZY_OSOBOWA", "CZY_RENTA",
                  "DATA_ZGLOSZENIA_RENTY"]


def classifier_(distinctive_types_):
    names_ = []
    state_changed_ = []
    is_assignment = []

    for name in distinctive_types_:
        folded = fold_text(name)
        found = False
        for pattern in DICT_:
            if fold_text(pattern) in folded:
                found = True
                break

        names_.append(name)
        state_changed_.append(found)
        is_assignment.append(fold_text(REAL_ADJUSTER_) in folded)

    return pl.DataFrame({
        "HISTORYTYPE": names_,
        "IS_STATE": state_changed_,
        "IS_ASSIGN": is_assignment,
    })


def adjuster_key_expr(col="ADJUSTER"):
    name = pl.col(col).fill_null("(brak)")
    name = name.str.replace_all(r"(?i)\(\s*nie\s+pracuje\s*\)", "")
    name = name.str.replace_all(r"\s+", " ")

    return name.str.strip_chars().str.to_uppercase().alias("ADJ")


def read_source(path):
    if path.suffix == ".parquet":
        return pl.scan_parquet(path)
    else:
        return pl.scan_csv(path, try_parse_dates=True)


def main():
    parser = stage_parser(__doc__, needs_source=True)
    parser.add_argument("--theta", type=float, default=None)
    args = parser.parse_args()

    args.work.mkdir(parents=True, exist_ok=True)
    banner(1, "prepare", args.work)

    if args.theta is None:
        cfg = Config()
    else:
        cfg = Config(theta_seconds=args.theta)
    cfg.save(args.work)

    events = read_source(args.src).select(INPUT_COLUMNS_)
    distinctive_types_ = events.select("HISTORYTYPE").unique().collect()
    lookup = classifier_(distinctive_types_["HISTORYTYPE"].to_list())

    events = events.with_columns(
        adjuster_key_expr(),
        pl.col("EVENTTIMESTAMP").cast(pl.Datetime("us")),
        pl.col("DATA_ZGLOSZENIA_RENTY").cast(pl.Datetime("us")),
    ).join(lookup.lazy(), on="HISTORYTYPE", how="left")

    claims_plan = events.group_by("CLAIMID").agg(
        pl.col("CZY_RZECZOWA").max().alias("PD"),
        pl.col("CZY_OSOBOWA").max().alias("BI"),
        pl.col("CZY_RENTA").max().alias("RENTA"),
        pl.col("DATA_ZGLOSZENIA_RENTY").min().alias("D_RENTA"),
    )
    touches_plan = events.group_by(["CLAIMID", "ADJ", "EVENTTIMESTAMP"]).agg(
        pl.col("IS_STATE").max().alias("IS_STATE"),
        pl.col("IS_ASSIGN").max().alias("IS_ASSIGN"),
    )

    claims, touches = pl.collect_all([claims_plan, touches_plan])

    claims.write_parquet(artifact(args.work, "claims"))
    touches.write_parquet(artifact(args.work, "touches"))
    unmatched = lookup.filter(~pl.col("IS_STATE"))["HISTORYTYPE"].to_list()

    done([artifact(args.work, "config"), artifact(args.work, "claims"),
          artifact(args.work, "touches")],
         {"touches": touches.height,
          "claims": claims.height,
          "annuity_claims": int(claims["RENTA"].sum()),
          "state_changing_share": round(float(touches["IS_STATE"].mean()), 4),
          "history_types": lookup.height,
          "not_state_changing": unmatched,
          "check": ""})


if __name__ == "__main__":
    main()


####TPend1
import polars as pl

from ulae_common import (Config, artifact, banner, done, require,
                         stage_parser, write_json)


def profile_users(touches, cfg):
    """One row per user, with the two exclusion flags worked out."""
    per_hour = (
        touches.with_columns(pl.col("EVENTTIMESTAMP").dt.truncate("1h").alias("HR"))
        .group_by(["ADJ", "HR"])
        .agg(pl.col("CLAIMID").n_unique().alias("C"))
        .group_by("ADJ")
        .agg(pl.col("C").max().alias("MAX_CLAIMS_PER_HOUR"))
    )

    profiles = touches.group_by("ADJ").agg(
        pl.col("CLAIMID").n_unique().alias("N_CLAIMS"),
        pl.len().alias("N_TOUCHES"),
        pl.col("IS_STATE").mean().alias("SHARE_STATE"),
        pl.col("IS_ASSIGN").any().alias("EVER_ASSIGNED"),
        pl.col("EVENTTIMESTAMP").min().alias("FIRST_SEEN"),
        pl.col("EVENTTIMESTAMP").max().alias("LAST_SEEN"),
    ).join(per_hour, on="ADJ", how="left")

    name_pattern = "|".join(cfg.robot_name_patterns)

    is_robot = (
        pl.col("ADJ").str.to_lowercase().str.contains(name_pattern)
        | (pl.col("MAX_CLAIMS_PER_HOUR") >= cfg.robot_claims_per_hour)
    )

    is_viewer = (
        ~pl.col("EVER_ASSIGNED")
        & (pl.col("SHARE_STATE") < cfg.viewer_max_state_share)
    )

    profiles = profiles.with_columns(
        is_robot.alias("IS_ROBOT"), is_viewer.alias("IS_VIEWER"))

    keep = ~pl.col("IS_ROBOT") & ~pl.col("IS_VIEWER")
    return profiles.with_columns(keep.alias("KEEP")).sort("ADJ")


def main():
    args = stage_parser(__doc__).parse_args()
    banner(2, "choose handlers", args.work)
    require(args.work, "touches")

    cfg = Config.load(args.work)
    touches = pl.read_parquet(artifact(args.work, "touches"))

    profiles = profile_users(touches, cfg)
    profiles.write_csv(artifact(args.work, "profiles"))

    kept = profiles.filter(pl.col("KEEP"))["ADJ"].to_list()
    write_json(args.work, "handlers", {"n": len(kept), "adjusters": kept})

    kept_touches = touches.filter(pl.col("ADJ").is_in(kept)).height

    done([artifact(args.work, "profiles"), artifact(args.work, "handlers")],
         {"users_total": profiles.height,
          "robots": int(profiles["IS_ROBOT"].sum()),
          "viewers": int(profiles["IS_VIEWER"].sum()),
          "users_kept": len(kept),
          "touches_kept": kept_touches,
          "share_kept": round(kept_touches / max(touches.height, 1), 4),
          "check": "spot-check named individuals in user_profiles.csv"})


if __name__ == "__main__":
    main()


#TPend2
import polars as pl

from ulae_common import (Config, artifact, attribute, banner, done,
                         handler_touches, require, segment_expr, stage_parser,
                         write_json)


def hours_by_segment(touches, claims, theta, cfg):
    attributed = attribute(touches, theta, cfg)
    attributed = attributed.join(claims, on="CLAIMID", how="left")
    attributed = attributed.with_columns(segment_expr())

    table = (attributed.group_by("SEGMENT")
             .agg((pl.col("DUR_S").sum() / 3600).alias("HOURS"))
             .sort("SEGMENT"))

    hours = {}
    for segment, value in zip(table["SEGMENT"], table["HOURS"]):
        hours[segment] = round(value, 1)
    measured = attributed.filter(pl.col("RAW_DUR").is_not_null()).height
    in_session = round(measured / max(attributed.height, 1), 4)

    return hours, in_session


def annuity_share(hours):
    bi = hours.get("BI", 0.0)
    renta = hours.get("RENTA", 0.0)

    if bi + renta == 0:
        return None

    return round(renta / (bi + renta), 4)


def main():
    parser = stage_parser(__doc__)
    parser.add_argument("--grid", type=float, nargs="*", default=None,
                        help="override the theta grid, in seconds")
    args = parser.parse_args()

    banner(3, "annuity share", args.work)
    require(args.work, "claims")

    cfg = Config.load(args.work)
    claims = pl.read_parquet(artifact(args.work, "claims"))
    touches = handler_touches(args.work)

    if args.grid:
        grid = args.grid
    else:
        grid = list(cfg.theta_grid)

    if cfg.theta_seconds not in grid:
        grid = sorted(grid + [cfg.theta_seconds])

    by_theta = {}
    for candidate in grid:
        hours, in_session = hours_by_segment(touches, claims, candidate, cfg)
        by_theta[int(candidate)] = {
            "hours": hours,
            "total_hours": round(sum(hours.values()), 0),
            "in_session_share": in_session,
            "annuity_share": annuity_share(hours),
        }

    chosen = by_theta[int(cfg.theta_seconds)]

    shares = []
    totals = []
    for row in by_theta.values():
        if row["annuity_share"] is not None:
            shares.append(row["annuity_share"])
        if row["total_hours"]:
            totals.append(row["total_hours"])

    if totals:
        hours_ratio = round(max(totals) / min(totals), 2)
    else:
        hours_ratio = None

    if shares:
        share_range = round(max(shares) - min(shares), 5)
    else:
        share_range = None

    payload = {
        "annuity_share": chosen["annuity_share"],
        "theta_used": cfg.theta_seconds,
        "hours": chosen["hours"],
        "in_session_share": chosen["in_session_share"],
        "sensitivity": {"by_theta": by_theta,
                        "hours_range_ratio": hours_ratio,
                        "share_range_abs": share_range},
        "interpretation":
            "",
    }

    done([write_json(args.work, "share", payload)],
         {"annuity_share": chosen["annuity_share"],
          "theta_used": cfg.theta_seconds,
          "hours": chosen["hours"],
          "in_session_share": chosen["in_session_share"],
          "hours_range_ratio": hours_ratio,
          "share_range_abs": share_range,
          "shares_by_theta": {k: v["annuity_share"]
                              for k, v in by_theta.items()}})


if __name__ == "__main__":
    main()


#tpend3
import argparse
import json
import unicodedata

from pathlib import Path
import polars as pl

class Config:

    def __init__(
        self,
        theta_seconds=600.0,
        theta_grid=(120, 300, 600, 1800, 7200),
        tail_quantile=0.5,
        robot_claims_per_hour=150,
        robot_name_patterns=("robot", "batch", "system", "u00", "svc", "srv"),
        viewer_max_state_share=0.05,
    ):
        self.theta_seconds = theta_seconds
        self.theta_grid = theta_grid
        self.tail_quantile = tail_quantile
        self.robot_claims_per_hour = robot_claims_per_hour
        self.robot_name_patterns = robot_name_patterns
        self.viewer_max_state_share = viewer_max_state_share

    def save(self, work):
        settings = {
            "theta_seconds": self.theta_seconds,
            "theta_grid": list(self.theta_grid),
            "tail_quantile": self.tail_quantile,
            "robot_claims_per_hour": self.robot_claims_per_hour,
            "robot_name_patterns": list(self.robot_name_patterns),
            "viewer_max_state_share": self.viewer_max_state_share,
        }
        (work / "config.json").write_text(json.dumps(settings, indent=2))

    @classmethod
    def load(cls, work):
        path = work / "config.json"
        if not path.exists():
            raise SystemExit(f"{path} not found. Run stage 1 first.")

        settings = json.loads(path.read_text())
        settings["theta_grid"] = tuple(settings["theta_grid"])
        settings["robot_name_patterns"] = tuple(settings["robot_name_patterns"])
        return cls(**settings)

ARTIFACTS = {
    "config":   "config.json",
    "claims":   "claims.parquet",
    "touches":  "touches.parquet",
    "profiles": "user_profiles.csv",
    "handlers": "handlers.json",
    "share":    "share.json",
}

ARTIFACT_OWNER = {"config": 1, "claims": 1, "touches": 1,
                  "profiles": 2, "handlers": 2, "share": 3}


def artifact(work, key):
    return work / ARTIFACTS[key]


def require(work, *keys):
    missing = []
    for key in keys:
        if not artifact(work, key).exists():
            missing.append(key)

    if not missing:
        return

    lines = ["Missing upstream artifacts:"]
    for key in missing:
        lines.append(f"  {artifact(work, key)}  "
                     f"(produced by stage {ARTIFACT_OWNER[key]})")
    raise SystemExit("\n".join(lines))


def read_json(work, key):
    return json.loads(artifact(work, key).read_text())


def write_json(work, key, payload):
    path = artifact(work, key)
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def handler_touches(work):
    require(work, "touches", "handlers")
    keep = read_json(work, "handlers")["adjusters"]
    return (pl.read_parquet(artifact(work, "touches"))
              .filter(pl.col("ADJ").is_in(keep)))

def fold_text(text):
    if text is None:
        return ""

    text = text.replace("ł", "l").replace("Ł", "L")

    text = unicodedata.normalize("NFKD", text)

    kept = ""
    for character in text:
        if unicodedata.combining(character) == 0:
            kept = kept + character

    return kept.lower().strip()

def attribute(touches, theta, cfg):
    timeline = touches.select("ADJ", "EVENTTIMESTAMP").unique()
    timeline = timeline.sort(["ADJ", "EVENTTIMESTAMP"])

    gap = (pl.col("EVENTTIMESTAMP").shift(-1) - pl.col("EVENTTIMESTAMP")).over("ADJ")
    timeline = timeline.with_columns(
        gap.dt.total_seconds().cast(pl.Float64).alias("GAP"))

    measured = pl.when(pl.col("GAP") <= theta).then(pl.col("GAP")).otherwise(None)
    timeline = timeline.with_columns(measured.alias("RAW_DUR"))

    result = touches.join(timeline, on=["ADJ", "EVENTTIMESTAMP"], how="left")
    result = result.with_columns(
        pl.len().over(["ADJ", "EVENTTIMESTAMP"]).alias("N_CONCURRENT"))

    tau = result["RAW_DUR"].drop_nulls().quantile(cfg.tail_quantile)
    if tau is None:
        tau = 60.0

    best = pl.coalesce(pl.col("RAW_DUR"), pl.lit(float(tau)))
    return result.with_columns((best / pl.col("N_CONCURRENT")).alias("DUR_S"))

def segment_expr():
    is_annuity_work = (
        (pl.col("RENTA") == 1)
        & pl.col("D_RENTA").is_not_null()
        & (pl.col("EVENTTIMESTAMP") >= pl.col("D_RENTA"))
    )

    return (
        pl.when(is_annuity_work).then(pl.lit("RENTA"))
        .when(pl.col("BI") == 1).then(pl.lit("BI"))
        .when(pl.col("PD") == 1).then(pl.lit("PD"))
        .otherwise(pl.lit("UNKNOWN"))
        .alias("SEGMENT")
    )

def stage_parser(description, needs_source=False):
    parser = argparse.ArgumentParser(description=description)
    if needs_source:
        parser.add_argument("src", type=Path, help="parquet or csv extract")
    parser.add_argument("-w", "--work", type=Path, default=Path("work"),
                        help="checkpoint directory shared by all stages")
    return parser


def banner(stage, title, work):
    print(f"[stage {stage}] {title}   work={work}")


def done(paths, summary=None):
    for path in paths:
        print(f"  wrote {path}")
    if summary:
        print(json.dumps(summary, indent=2, default=str))

#TPendcommon
import argparse
import subprocess
import sys

from pathlib import Path


HERE = Path(__file__).parent
STAGES = {1: "s1_prepare.py", 2: "s2_handlers.py", 3: "s3_share.py"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path, nargs="?", default=None,
                        help="parquet or csv extract (stage 1 only)")
    parser.add_argument("-w", "--work", type=Path, default=Path("work"))
    parser.add_argument("--from", dest="first", type=int, default=1)
    parser.add_argument("--to", dest="last", type=int, default=3)

    args, extra = parser.parse_known_args()

    if args.first < 1 or args.last > 3 or args.first > args.last:
        raise SystemExit(f"invalid range --from {args.first} --to {args.last}")

    if args.first == 1 and args.src is None:
        raise SystemExit("stage 1 needs the source extract. Give it as the "
                         "first argument, or start higher with --from.")

    for number in range(args.first, args.last + 1):
        if number == 1:
            arguments = [str(args.src), "-w", str(args.work)] + extra
        else:
            arguments = ["-w", str(args.work)]

        result = subprocess.run(
            [sys.executable, str(HERE / STAGES[number])] + arguments)

        if result.returncode != 0:
            raise SystemExit(f"\n{STAGES[number]} failed. Stopping.")

    print(f"\ndone; the answer is in {args.work}/share.json")


if __name__ == "__main__":
    main()

#TPrunall