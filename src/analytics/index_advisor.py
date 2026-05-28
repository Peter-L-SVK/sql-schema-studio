# ----------------------------------------------------------------------
# SQL Schema Studio 0.5 - ML Index Advisor (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
ML-based index recommendations using scikit-learn
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from pathlib import Path
from typing import Dict, Any


class MLIndexAdvisor:
    """Index recommendation engine using scikit-learn"""

    def __init__(self, model_path: str | None = None):
        self.scaler = StandardScaler()
        self.index_classifier = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42
        )
        self.improvement_regressor = GradientBoostingRegressor(
            n_estimators=100, max_depth=5, random_state=42
        )
        self.is_trained = False

        if model_path and Path(model_path).exists():
            self.load_model(model_path)

    def load_model(self, path: str) -> None:
        """Load model from disk (not yet implemented)"""
        pass

    def extract_features(self, table_stats: Dict[str, Any]) -> np.ndarray:
        """Convert PostgreSQL table statistics to feature vector"""
        features = [
            table_stats.get("n_tup_ins", 0),
            table_stats.get("n_tup_upd", 0),
            table_stats.get("n_tup_del", 0),
            table_stats.get("n_live_tup", 0),
            table_stats.get("n_dead_tup", 0),
            table_stats.get("seq_scan", 0),
            table_stats.get("idx_scan", 0),
            table_stats.get("seq_tup_read", 0),
            table_stats.get("idx_tup_fetch", 0),
            table_stats.get("n_tup_ins", 0) / max(table_stats.get("n_live_tup", 1), 1),
            table_stats.get("n_tup_upd", 0) / max(table_stats.get("n_live_tup", 1), 1),
            table_stats.get("n_dead_tup", 0) / max(table_stats.get("n_live_tup", 1), 1),
            table_stats.get("idx_scan", 0) / max(table_stats.get("seq_scan", 1), 1),
        ]
        return np.array(features)

    def train(self, training_data: pd.DataFrame):
        """Train the model with historical data"""
        X = np.vstack(training_data["features"].values)
        y_index = training_data["has_index"].values
        y_improvement = training_data["improvement_pct"].values

        X_scaled = self.scaler.fit_transform(X)

        # Split data
        X_train, X_test, y_idx_train, y_idx_test = train_test_split(
            X_scaled, y_index, test_size=0.2, random_state=42
        )

        # Train classifier
        self.index_classifier.fit(X_train, y_idx_train)

        # Train improvement predictor
        X_imp_train, X_imp_test, y_imp_train, y_imp_test = train_test_split(
            X_scaled, y_improvement, test_size=0.2, random_state=42
        )
        self.improvement_regressor.fit(X_imp_train, y_imp_train)

        self.is_trained = True

        # Calculate accuracy
        idx_accuracy = self.index_classifier.score(X_test, y_idx_test)
        imp_score = self.improvement_regressor.score(X_imp_test, y_imp_test)

        return {"classifier_accuracy": idx_accuracy, "regressor_r2_score": imp_score}

    def predict_index_need(self, features: np.ndarray) -> float:
        """Predict probability that an index is needed"""
        if not self.is_trained:
            return 0.5

        features_scaled = self.scaler.transform(features.reshape(1, -1))
        proba = self.index_classifier.predict_proba(features_scaled)
        return float(proba[0][1])  # Probability of class 1 (index needed)
