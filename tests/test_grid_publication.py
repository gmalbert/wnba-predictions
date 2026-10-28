import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from scripts import export_web_data
from utils import prediction_engine as engine
from utils import data_fetcher
from utils.data_contracts import PREDICTION_COLUMNS
from utils.redaction import redact_error


class GridPublicationTests(unittest.TestCase):
    def test_empty_success_publishes_a_new_snapshot_and_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "web"
            output.mkdir()
            with patch.object(engine, "get_odds", return_value=pd.DataFrame()), patch.object(engine, "predict_season_games", return_value=pd.DataFrame(columns=PREDICTION_COLUMNS)), patch.object(engine, "predictions_dir", return_value=root), patch.object(engine, "_now", return_value="2026-10-28T12:00:00Z"), patch.object(engine, "freeze_prediction_ledger") as ledger:
                engine.generate_and_store_predictions(2026, stage="pre_tip", as_of="2026-10-28T12:00:00Z")
                ledger.assert_not_called()
            with patch.object(export_web_data, "_predictions_dir", return_value=root):
                export_web_data.export_predictions(output)
            data = json.loads((output / "predictions.json").read_text())
            self.assertEqual(data["games"], [])
            self.assertEqual(data["generated_at"], "2026-10-28T12:00:00Z")
            self.assertEqual(data["status"], "no_picks")

    def test_failed_schedule_does_not_mean_no_games(self):
        with patch.object(engine, "load_regression_model"), patch.object(engine, "load_distribution_calibrator"), patch.object(engine, "load_eval_metrics", return_value={}), patch.object(engine, "get_schedule", return_value=pd.DataFrame()):
            with self.assertRaisesRegex(RuntimeError, "schedule is unavailable"):
                engine.predict_season_games(2026, models={}, elo=object(), as_of="2026-10-28T12:00:00Z")

    def test_completed_schedule_does_not_require_live_player_stats(self):
        with patch.object(engine, "load_regression_model"), patch.object(engine, "load_distribution_calibrator"), patch.object(engine, "load_eval_metrics", return_value={}), patch.object(engine, "get_schedule", return_value=pd.DataFrame({"game_date": ["2026-09-24"]})), patch.object(engine, "_latest_feature_data") as features:
            result = engine.predict_season_games(2026, models={}, elo=object(), as_of="2026-10-28T12:00:00Z")
            self.assertTrue(result.empty)
            features.assert_not_called()

    def test_credentials_are_removed_from_new_and_existing_health_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "health.json"
            path.write_text(json.dumps([{"source": "old", "data_type": "odds", "error": "https://provider?apiKey=secret-old&event=1"}]))
            with patch.object(data_fetcher, "health_path", return_value=path):
                data_fetcher._record_health("new", "odds", False, error="https://provider?api_key=secret-new&event=2")
            saved = path.read_text()
            self.assertNotIn("secret-old", saved)
            self.assertNotIn("secret-new", saved)
            self.assertIn("event=2", saved)
        self.assertIsNone(redact_error(None))


if __name__ == "__main__":
    unittest.main()
