"""
Tests that a controller timeout in server-mode (parallel=True) leaves the
pythonDB reachable and other controllers unaffected.

This reproduces the scenario the server.py _fmlc_loop drives: parallel=True,
one controller sleeping past its timeout while a sibling keeps computing.
"""

import sys
import time
import pandas as pd
from os import path

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from fmlc.stackedclasses import controller_stack
from fmlc.modules.dummy_modules import Multiplier, TimeoutDummy


def test_parallel_timeout_behaviour():
    """
    After a controller times out in parallel mode (as driven by server.py):
    - the pythonDB is still reachable,
    - the timed-out worker is replaced by a fresh live process,
    - sibling controllers keep producing correct results,
    - the timed-out controller has only its init record.
    """
    controller = {
        'fast': {'function': Multiplier, 'sampletime': 1},
        'slow': {'function': TimeoutDummy, 'sampletime': 1},
    }
    mapping = {
        'fast_a': 10,
        'fast_b': 4,
        'fast_delay': None,
        'fast_timeout': None,
        # TimeoutDummy sleeps 2.1 s; timeout is 1 s so it always times out.
        'slow_delay': 2.1,
        'slow_timeout': 1,
    }
    stack = controller_stack(controller, mapping, tz=0, debug=False, parallel=True)
    try:
        # _workers[0] is the single _Worker inside the 'slow' ProcessWorkerPipe
        inner_before = stack.pworkers['slow']._workers[0]  # pylint: disable=protected-access
        pid_before = inner_before.pid

        stack.run_query_control_for(4, shutdown=False)

        inner_after = stack.pworkers['slow']._workers[0]  # pylint: disable=protected-access

        # 1. pythonDB is still reachable after the timeout
        assert stack.database.test_db() == 999, \
            'pythonDB is unreachable after a controller timeout'

        # 2. Timed-out worker process was restarted with a new PID
        assert inner_after.pid != pid_before, \
            'Timed-out worker was not restarted (PID unchanged)'
        assert inner_after.is_alive(), \
            'Restarted worker process is not alive'

        # 3. Sibling controller ran multiple successful steps
        df_fast = pd.DataFrame(stack.log_to_df()['fast'])
        assert df_fast.shape[0] > 1, \
            'Fast controller produced no results while sibling timed out'
        assert list(df_fast['c'])[1:] == [40.0] * (df_fast.shape[0] - 1), \
            'Fast controller computed wrong results'

        # 4. Timed-out controller has only the init record (never finished)
        df_slow = pd.DataFrame(stack.log_to_df()['slow'])
        assert df_slow.shape[0] == 1, \
            f'Timed-out controller should have 1 record (init only), got {df_slow.shape[0]}'
    finally:
        stack.shutdown()


def test_pythondb_reachable_after_serial_run():
    """pythonDB must still respond after a normal run in serial mode."""
    controller = {
        'fast': {'function': Multiplier, 'sampletime': 1},
    }
    mapping = {
        'fast_a': 10,
        'fast_b': 4,
        'fast_delay': None,
        'fast_timeout': None,
    }
    stack = controller_stack(controller, mapping, tz=0, debug=False, parallel=False)
    try:
        for _ in range(3):
            stack.query_control(time.time())
            time.sleep(1.2)

        assert stack.database.test_db() == 999, \
            'pythonDB is unreachable after serial run'
    finally:
        stack.shutdown()
