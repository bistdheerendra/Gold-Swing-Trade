"""Classification / regression / trading research metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


def classification_metrics(y_true: Sequence[Any], y_pred: Sequence[Any]) -> Dict[str, Any]:
    yt = [str(x) for x in y_true]
    yp = [str(x) for x in y_pred]
    n = len(yt) or 1
    acc = sum(a == b for a, b in zip(yt, yp)) / n
    labels = sorted(set(yt) | set(yp))
    # macro F1
    f1s = []
    precisions = []
    recalls = []
    cm = {a: {b: 0 for b in labels} for a in labels}
    for a, b in zip(yt, yp):
        cm[a][b] += 1
    for lab in labels:
        tp = cm[lab][lab]
        fp = sum(cm[o][lab] for o in labels if o != lab)
        fn = sum(cm[lab][o] for o in labels if o != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
    # balanced accuracy
    recalls_bal = []
    for lab in labels:
        support = sum(cm[lab].values())
        if support == 0:
            continue
        recalls_bal.append(cm[lab][lab] / support)
    bal = float(np.mean(recalls_bal)) if recalls_bal else 0.0
    return {
        "accuracy": round(acc, 6),
        "balanced_accuracy": round(bal, 6),
        "precision_macro": round(float(np.mean(precisions)) if precisions else 0.0, 6),
        "recall_macro": round(float(np.mean(recalls)) if recalls else 0.0, 6),
        "f1_macro": round(float(np.mean(f1s)) if f1s else 0.0, 6),
        "confusion_matrix": cm,
        "support": dict(Counter(yt)),
        "n": len(yt),
    }


def regression_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> Dict[str, Any]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]
    if len(yt) == 0:
        return {"mae": None, "rmse": None, "r2": None, "directional_accuracy": None, "n": 0}
    mae = float(np.mean(np.abs(yt - yp)))
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    dir_acc = float(np.mean((np.sign(yt) == np.sign(yp)).astype(float)))
    return {
        "mae": round(mae, 8),
        "rmse": round(rmse, 8),
        "r2": round(r2, 6),
        "directional_accuracy": round(dir_acc, 6),
        "n": int(len(yt)),
    }


def trading_metrics_from_r(net_rs: Sequence[float]) -> Dict[str, Any]:
    rs = [float(x) for x in net_rs if x is not None and np.isfinite(float(x))]
    if not rs:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_r": 0.0,
            "average_r": 0.0,
            "net_r": 0.0,
            "max_drawdown_r": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "longest_winning_streak": 0,
            "longest_losing_streak": 0,
        }
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    net = sum(rs)
    n = len(rs)
    # equity in R units
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    w_streak = l_streak = max_w = max_l = 0
    for r in rs:
        if r > 0:
            w_streak += 1
            l_streak = 0
            max_w = max(max_w, w_streak)
        elif r < 0:
            l_streak += 1
            w_streak = 0
            max_l = max(max_l, l_streak)
        else:
            w_streak = l_streak = 0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)
    return {
        "trades": n,
        "win_rate": round(len(wins) / n, 6),
        "profit_factor": round(min(pf, 999.0), 6),
        "expectancy_r": round(net / n, 6),
        "average_r": round(net / n, 6),
        "net_r": round(net, 6),
        "max_drawdown_r": round(max_dd, 6),
        "average_win": round(sum(wins) / len(wins), 6) if wins else 0.0,
        "average_loss": round(abs(sum(losses) / len(losses)), 6) if losses else 0.0,
        "longest_winning_streak": max_w,
        "longest_losing_streak": max_l,
    }


def overfitting_flag(train_score: float, val_score: float, *, gap: float = 0.15) -> Optional[str]:
    if train_score - val_score >= gap:
        return "POSSIBLE_OVERFIT"
    return None


def calibration_buckets(
    y_true: Sequence[Any],
    proba: np.ndarray,
    classes: Sequence[str],
    positive_class: Optional[str] = None,
) -> Dict[str, Any]:
    """Simple reliability buckets for a chosen positive class (default last class)."""
    classes = list(classes)
    if not classes or proba is None or len(proba) == 0:
        return {"buckets": [], "brier": None, "log_loss": None}
    pos = positive_class or classes[-1]
    if pos not in classes:
        return {"buckets": [], "brier": None, "log_loss": None}
    idx = classes.index(pos)
    p = proba[:, idx]
    y = np.asarray([1.0 if str(t) == pos else 0.0 for t in y_true])
    edges = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
    buckets = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi)
        if mask.sum() == 0:
            continue
        buckets.append(
            {
                "range": f"{lo:.2f}-{hi:.2f}" if hi <= 1 else f"{lo:.2f}-1.00",
                "count": int(mask.sum()),
                "avg_pred": round(float(p[mask].mean()), 4),
                "avg_true": round(float(y[mask].mean()), 4),
            }
        )
    brier = float(np.mean((p - y) ** 2))
    # clip for log loss
    eps = 1e-9
    pp = np.clip(p, eps, 1 - eps)
    logloss = float(-np.mean(y * np.log(pp) + (1 - y) * np.log(1 - pp)))
    return {"buckets": buckets, "brier": round(brier, 6), "log_loss": round(logloss, 6), "positive_class": pos}
