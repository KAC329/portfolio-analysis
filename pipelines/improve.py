"""Self-improvement loop: one iteration = N new experiments vs the champion.

Rules that keep the loop honest (they are the point of this file):
1. Selection uses the VALIDATION split only. The hold-out (from HOLDOUT_START)
   is reported at each check-in but never drives a decision.
2. A challenger must beat the champion's validation ICIR by ``MARGIN``.
   Tiny gains are usually noise from trying many configurations.
3. Every trial is logged (results/metrics/scoreboard.jsonl), so the total
   number of attempts is visible — the more you try, the more a lucky result is
   expected by chance (multiple-testing / "data-snooping" bias).

Usage:  python improve.py --trials 3
"""
from __future__ import annotations

import argparse
import json
import random

import pandas as pd

from common import C, load_all
from p3_signal_research import RETRAIN, build
from pa.metrics import log_returns
from pa.models import WFConfig, log_scoreboard, split_scores, walk_forward

MARGIN = 0.05
CHAMP = C.METRICS / "champion.json"
CHECKINS = C.METRICS / "checkins.md"

SPACE = {
    "xgb": {"max_depth": [2, 3, 4, 5], "n_estimators": [150, 300, 600], "learning_rate": [0.01, 0.03, 0.06],
            "min_child_weight": [20, 50, 100, 200], "subsample": [0.6, 0.8, 1.0],
            "colsample_bytree": [0.5, 0.7, 1.0], "reg_lambda": [1.0, 5.0, 20.0]},
    "ridge": {"alpha": [0.1, 1, 10, 100, 1000, 10000]},
    "lstm": {"hidden": [16, 32, 64], "epochs": [5, 8, 12], "lr": [5e-4, 1e-3, 3e-3]},
}
TRAIN_WINDOWS = [None, 756, 1260]


def n_trials_so_far() -> int:
    p = C.METRICS / "scoreboard.jsonl"
    return sum(1 for _ in open(p)) if p.exists() else 0


def sample(rng) -> WFConfig:
    model = rng.choices(["xgb", "ridge", "lstm"], weights=[0.6, 0.2, 0.2])[0]
    params = {k: rng.choice(v) for k, v in SPACE[model].items()}
    return WFConfig(model, params, retrain_every=RETRAIN.get(model, C.RETRAIN_EVERY),
                    train_window=rng.choice(TRAIN_WINDOWS))


def current_champion() -> dict | None:
    if CHAMP.exists():
        return json.loads(CHAMP.read_text())
    p3 = C.METRICS / "p3.json"
    if not p3.exists():
        return None
    r = json.loads(p3.read_text())
    m = r["best_model_by_validation"]
    champ = {"model": m, "params": {}, "train_window": None, "scores": r["scores"][m], "source": "p3 baseline"}
    src = C.METRICS / f"oos_{m}.parquet"
    if src.exists():
        pd.read_parquet(src).to_parquet(C.METRICS / "oos_champion.parquet")
    CHAMP.write_text(json.dumps(champ, indent=2, default=float))
    return champ


def checkin(text: str):
    with open(CHECKINS, "a") as fh:
        fh.write(text + "\n")
    print(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else n_trials_so_far()
    rng = random.Random(seed)

    close, volume, market, fred, rets, rf = load_all()
    panel = build(close, volume, market, fred)
    champ = current_champion()
    best_icir = champ["scores"]["validation"]["ICIR_ann"] if champ else float("-inf")
    promoted = None
    for i in range(a.trials):
        cfg = sample(rng)
        print(f"trial {i + 1}/{a.trials}: {cfg.model} {cfg.params} window={cfg.train_window}")
        oos = walk_forward(panel, cfg, raw_returns=log_returns(close))
        sc = split_scores(oos)
        log_scoreboard({"tag": f"loop-seed{seed}", "model": cfg.model, "params": cfg.params,
                        "train_window": cfg.train_window, "horizon": C.HORIZON,
                        **{f"{k}_{s}": v for s, d in sc.items() for k, v in d.items()}})
        v = sc["validation"]
        print(f"   val ICIR {v['ICIR_ann']:+.3f} IC {v['mean_IC']:+.4f} hit {v['hit_rate']:.3f}  (champion {best_icir:+.3f})")
        if v["ICIR_ann"] > best_icir + MARGIN:
            best_icir = v["ICIR_ann"]
            promoted = {"model": cfg.model, "params": cfg.params, "train_window": cfg.train_window,
                        "scores": sc, "source": f"loop-seed{seed}-trial{i + 1}"}
            oos.to_parquet(C.METRICS / "oos_champion.parquet")
    if promoted:
        old = champ["scores"] if champ else None
        CHAMP.write_text(json.dumps(promoted, indent=2, default=float))
        v, h = promoted["scores"]["validation"], promoted["scores"]["holdout"]
        ov = old["validation"] if old else {}
        oh = old["holdout"] if old else {}
        checkin(
            f"\n### {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC — new champion: {promoted['model']}\n"
            f"- Params: `{promoted['params']}`, train window: {promoted['train_window'] or 'expanding'}\n"
            f"- Validation ICIR {ov.get('ICIR_ann', float('nan')):+.3f} → **{v['ICIR_ann']:+.3f}**, "
            f"mean IC {ov.get('mean_IC', float('nan')):+.4f} → {v['mean_IC']:+.4f}, "
            f"hit rate {ov.get('hit_rate', float('nan')):.1%} → {v['hit_rate']:.1%}\n"
            f"- Hold-out (not used for selection): IC {oh.get('mean_IC', float('nan')):+.4f} → {h.get('mean_IC', float('nan')):+.4f}, "
            f"hit rate {oh.get('hit_rate', float('nan')):.1%} → {h.get('hit_rate', float('nan')):.1%}\n"
            f"- Total experiments logged so far: {n_trials_so_far()}")
        print("PROMOTED")
    else:
        print(f"no promotion this iteration (champion ICIR {best_icir:+.3f}, total trials {n_trials_so_far()})")


if __name__ == "__main__":
    main()
