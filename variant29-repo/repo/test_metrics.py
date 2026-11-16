"""Проверка metrics.py на контрольном примере из задания: 20 запросов за 10 с."""
import os, unittest

import metrics

SAMPLE = os.path.join(os.path.dirname(__file__), "results", "sample20.csv")


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.m = metrics.compute(metrics.read_rows(SAMPLE))

    def test_pofod(self):
        self.assertAlmostEqual(self.m["POFOD"], 0.30)

    def test_rocof(self):
        self.assertEqual(self.m["episodes"], 1)
        self.assertAlmostEqual(self.m["ROCOF_per_h"], 360.0)

    def test_avail(self):
        self.assertAlmostEqual(self.m["AVAIL"], 0.70)

    def test_percentiles(self):
        self.assertEqual((self.m["p50_ms"], self.m["p95_ms"], self.m["p99_ms"]), (45, 1003, 1004))

    def test_episode_split_by_gap(self):
        self.assertEqual(metrics.count_episodes([0.0, 1.0, 2.9, 10.0, 11.5]), 2)


if __name__ == "__main__":
    unittest.main()
