"""Модульные тесты паттерна «Bulkhead + приоритет аварийных команд» (вариант 29).

Работают без кластера: настоящие call_dep / call_backup подменяются функциями,
которые «тормозят» или падают. Запуск: python -m unittest -v
"""
import threading, time, unittest

import core


def slow_dep(timeout=10.0):            # зависимость «тормозит» (как delay_ms=3000)
    time.sleep(min(timeout, 3.0))
    raise TimeoutError("dep-a slow")


def fast_dep(timeout=10.0):
    return {"source": "dep-a", "value": 42}


def fast_backup(timeout=10.0):
    return {"source": "dep-b", "value": 7}


def broken_backup(timeout=10.0):
    raise ConnectionError("dep-b down")


class BulkheadPatternTest(unittest.TestCase):
    def setUp(self):
        self._saved = (core.call_dep, core.call_backup, core.PATTERN,
                       core.NORMAL_POOL, core.EMERGENCY_POOL,
                       core.NORMAL_TIMEOUT, core.EMERGENCY_TIMEOUT)
        core.PATTERN = True
        core.NORMAL_TIMEOUT = 0.8
        core.EMERGENCY_TIMEOUT = 0.5
        core.NORMAL_POOL = threading.BoundedSemaphore(2)
        core.EMERGENCY_POOL = threading.BoundedSemaphore(2)
        core.call_backup = fast_backup

    def tearDown(self):
        (core.call_dep, core.call_backup, core.PATTERN, core.NORMAL_POOL,
         core.EMERGENCY_POOL, core.NORMAL_TIMEOUT, core.EMERGENCY_TIMEOUT) = self._saved

    # Правило 1: обычный отсек ограничен, лишние запросы отклоняются сразу.
    def test_normal_compartment_full_rejects_immediately(self):
        core.call_dep = slow_dep
        threads = [threading.Thread(target=core.do_work, args=("normal",)) for _ in range(2)]
        for t in threads:
            t.start()
        time.sleep(0.1)                                  # оба слота заняты
        start = time.time()
        with self.assertRaises(core.BulkheadFull):
            core.do_work("normal")
        self.assertLess(time.time() - start, 0.05)       # отказ мгновенный, без ожидания
        for t in threads:
            t.join()

    # Правило 2: перегрузка обычного отсека не мешает аварийной команде.
    def test_emergency_not_blocked_by_full_normal_compartment(self):
        core.call_dep = slow_dep
        threads = [threading.Thread(target=core.do_work, args=("normal",)) for _ in range(2)]
        for t in threads:
            t.start()
        time.sleep(0.1)
        start = time.time()
        r = core.do_work("emergency")
        self.assertEqual(r["status"], "ok")
        self.assertLess(time.time() - start, 1.5)        # пользователь ждёт не дольше 1,5 с
        for t in threads:
            t.join()

    # Правило 3: обычный запрос к медленной зависимости — ответ «отложено» за таймаут.
    def test_slow_dep_normal_request_deferred_within_timeout(self):
        core.call_dep = slow_dep
        start = time.time()
        r = core.do_work("normal")
        elapsed = time.time() - start
        self.assertEqual(r["status"], "deferred")
        self.assertLess(elapsed, 1.0)
        # поток освобождён: оба слота снова свободны
        self.assertTrue(core.NORMAL_POOL.acquire(blocking=False))
        self.assertTrue(core.NORMAL_POOL.acquire(blocking=False))

    # Правило 4: аварийная команда при отказе dep-a уходит по резервному каналу.
    def test_emergency_fails_over_to_backup_channel(self):
        core.call_dep = slow_dep
        start = time.time()
        r = core.do_work("emergency")
        self.assertEqual(r["channel"], "backup")
        self.assertEqual(r["source"], "dep-b")
        self.assertLess(time.time() - start, 1.5)

    # Правило 4 (обратная сторона): обычные запросы резервный канал не используют.
    def test_normal_request_never_uses_backup_channel(self):
        core.call_dep = slow_dep
        used = []
        core.call_backup = lambda timeout=1.0: used.append(1) or fast_backup()
        core.do_work("normal")
        self.assertEqual(used, [])

    # Аварийный отсек тоже ограничен: при отказе обоих каналов — явная ошибка, а не зависание.
    def test_emergency_both_channels_down_raises_fast(self):
        core.call_dep = slow_dep
        core.call_backup = broken_backup
        start = time.time()
        with self.assertRaises(ConnectionError):
            core.do_work("emergency")
        self.assertLess(time.time() - start, 1.5)

    # Исправная зависимость: обычный ответ, без деградации.
    def test_healthy_dep_returns_normal_answer(self):
        core.call_dep = fast_dep
        self.assertEqual(core.do_work("normal")["status"], "ok")
        r = core.do_work("emergency")
        self.assertEqual((r["status"], r["channel"]), ("ok", "primary"))

    # PATTERN=off — прямой вызов зависимости без отсеков.
    def test_pattern_off_calls_dep_directly(self):
        core.PATTERN = False
        core.call_dep = fast_dep
        self.assertEqual(core.do_work(), {"source": "dep-a", "value": 42})

    # Классификация трафика: каждый EMERGENCY_EVERY-й запрос — аварийная команда.
    def test_every_nth_request_is_emergency(self):
        saved_seq, saved_every = core._SEQ, core.EMERGENCY_EVERY
        try:
            core._SEQ = iter(range(1, 21))
            core.EMERGENCY_EVERY = 10
            kinds = [core.next_kind() for _ in range(20)]
            self.assertEqual(kinds.count("emergency"), 2)
            self.assertEqual(kinds[9], "emergency")
        finally:
            core._SEQ, core.EMERGENCY_EVERY = saved_seq, saved_every


if __name__ == "__main__":
    unittest.main()
