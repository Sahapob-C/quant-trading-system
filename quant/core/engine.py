"""The event loop that ties every component together.

The loop pulls bars from the data handler, then drains the event queue,
dispatching each event to the component that cares about it. The exact same
dispatch is reused for live trading — only the data handler and execution
handler are swapped (see ``quant/execution`` and ``quant/data``).

Ordering within one bar (this is what removes look-ahead bias):
  1. ``execution.on_new_bar`` fills orders queued on the *previous* bar, at this
     bar's open (backtest simulator; a no-op for live brokers).
  2. ``strategy.calculate_signals`` reacts to the new bar -> emits signals.
  3. signals -> orders -> the simulator *queues* them for the next bar's open.
  4. after the queue drains, ``portfolio.update_timeindex`` marks the book to the
     bar's close, with this bar's fills already applied.
"""
from __future__ import annotations

import queue
import time

from quant.core.events import EventType


class TradingEngine:
    def __init__(
        self,
        events: "queue.Queue",
        data_handler,
        strategy,
        portfolio,
        execution_handler,
        heartbeat: float = 0.0,
    ) -> None:
        self.events = events
        self.data_handler = data_handler
        self.strategy = strategy
        self.portfolio = portfolio
        self.execution_handler = execution_handler
        self.heartbeat = heartbeat
        self._bar_processed = False

    # ------------------------------------------------------------------
    def _dispatch(self) -> None:
        """Drain and route every event currently on the queue."""
        while True:
            try:
                event = self.events.get(False)
            except queue.Empty:
                break
            if event is None:
                continue

            if event.type == EventType.MARKET:
                self._bar_processed = True
                # Fill orders queued on the previous bar at this bar's open
                # (backtest). Live brokers fill immediately, so this is a no-op.
                self.execution_handler.on_new_bar(event)
                self.strategy.calculate_signals(event)
            elif event.type == EventType.SIGNAL:
                self.portfolio.update_signal(event)
            elif event.type == EventType.ORDER:
                self.execution_handler.execute_order(event)
            elif event.type == EventType.FILL:
                self.portfolio.update_fill(event)

    # ------------------------------------------------------------------
    def run_backtest(self) -> int:
        """Step through all historical bars. Returns the number of bars seen."""
        bars = 0
        while self.data_handler.continue_backtest:
            self._bar_processed = False
            self.data_handler.update_bars()
            self._dispatch()
            if self._bar_processed:
                self.portfolio.update_timeindex()  # mark to market after fills
                bars += 1
            if self.heartbeat:
                time.sleep(self.heartbeat)
        return bars

    # ------------------------------------------------------------------
    def run_live(self, poll_interval: float = 60.0, max_iterations=None, on_iteration=None) -> int:
        """Poll a live data feed forever, dispatching events as bars arrive.

        Identical dispatch logic to ``run_backtest``. ``on_iteration(i)`` is called
        after each poll (e.g. to snapshot state). Stop with Ctrl-C.
        """
        iterations = 0
        try:
            while True:
                self._bar_processed = False
                self.data_handler.update_bars()
                self._dispatch()
                if self._bar_processed:
                    self.portfolio.update_timeindex()
                iterations += 1
                if on_iteration is not None:
                    on_iteration(iterations)
                if max_iterations is not None and iterations >= max_iterations:
                    break
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\nStopped by user (Ctrl-C).")
        return iterations
