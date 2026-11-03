#!/usr/bin/env bash
# Rebuild every phase from raw data. Add --refresh to re-download prices first.
set -euo pipefail
cd "$(dirname "$0")/pipelines"
if [[ "${1:-}" == "--refresh" ]]; then
  python3 -c "from common import load_all; load_all(refresh=True)"
fi
python3 -m pytest -q ../tests
python3 p1_portfolio_analysis.py
python3 p2_optimization.py
python3 p3_signal_research.py
python3 p4_risk_management.py
python3 p5_black_litterman.py
