# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Asynchonous worker module.
"""

import os
import signal
import threading
import traceback
from multiprocessing import Process, Pipe


def _worker_process(conn, initializer, initargs):
    """
    Persistent worker loop. Receives (fn, args, kwargs) tuples,
    sends back (True, result) or (False, exception_string).
    """
    if initializer is not None:
        initializer(*initargs)
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            # parent closed the connection, shutdown
            break
        if msg is None:
            # explicit shutdown
            break

        fn, args, kwargs = msg
        try:
            result = fn(*args, **kwargs)
            conn.send((True, result))
        except Exception:  # pylint: disable=broad-exception-caught
            conn.send((False, traceback.format_exc()))


class _Worker:
    """Wraps a single persistent child process with its Pipe connection."""

    def __init__(self, initializer=None, initargs=()):
        self.initializer = initializer
        self.initargs = initargs
        # one task at a time per worker
        self._lock = threading.Lock()
        self._busy = False
        self._proc = None
        self._parent_conn = None
        self._start()

    def _start(self):
        parent_conn, child_conn = Pipe()
        proc = Process(
            target=_worker_process,
            args=(child_conn, self.initializer, self.initargs),
            daemon=True,
        )
        proc.start()
        child_conn.close()
        self._proc = proc
        self._parent_conn = parent_conn

    @property
    def pid(self):
        """Process ID of the worker."""
        return self._proc.pid if self._proc else None

    @property
    def busy(self):
        """True if the worker is currently executing a task."""
        return self._busy

    def is_alive(self):
        """Return True if the worker process is alive."""
        return self._proc is not None and self._proc.is_alive()

    def restart(self):
        """Kill and replace this worker only."""
        self._kill()
        self._start()
        self._busy = False

    def _kill(self):
        try:
            if self._proc and self._proc.is_alive():
                os.kill(self._proc.pid, signal.SIGKILL)
                self._proc.join(timeout=2)
        except (ProcessLookupError, OSError):
            pass
        try:
            self._parent_conn.close()
        except OSError:
            pass

    def run_task(self, fn, args, kwargs, timeout):
        """
        Send a task to this worker and wait up to `timeout` seconds.
        Returns (True, result) or raises TimeoutError / RuntimeError.
        This is called from a thread so blocking here is fine.
        """
        with self._lock:
            self._busy = True
            try:
                self._parent_conn.send((fn, args, kwargs))
                if self._parent_conn.poll(timeout):
                    success, payload = self._parent_conn.recv()
                    if success:
                        return payload
                    raise RuntimeError(
                        f"Worker raised an exception:\n{payload}"
                    )
                raise TimeoutError(
                    f"Worker {self._proc.pid} timed after {timeout}s"
                )
            finally:
                self._busy = False

    def shutdown(self):
        """Shutdown the worker process and clean up resources."""
        try:
            self._parent_conn.send(None)
        except OSError:
            pass
        self._proc.join(timeout=2)
        self._kill()


class ProcessWorkerPipe:
    """
    Pool of persistent workers. Each worker is managed individually,
    so a timeout kills and restarts only the offending process.
    """

    def __init__(self, max_workers=1, initializer=None, initargs=()):
        self._initializer = initializer
        self._initargs = initargs
        self._lock = threading.Lock()
        self._workers = [
            _Worker(initializer, initargs) for _ in range(max_workers)
        ]

    def _get_free_worker(self, poll_interval=0.05, acquire_timeout=None):
        """
        Block until a worker is free, then return it with its lock held
        (via the worker's own _busy flag under self._lock).
        """
        elapsed = 0.0
        while True:
            with self._lock:
                for w in self._workers:
                    if not w.busy and w.is_alive():
                        w._busy = True  #pylint: disable=protected-access
                        return w
            threading.Event().wait(poll_interval)
            elapsed += poll_interval
            if acquire_timeout is not None and elapsed >= acquire_timeout:
                raise TimeoutError("No free worker became available in time.")

    def submit(self, fn, *args, timeout=None, **kwargs):
        """
        Submit a task. Blocks until a worker is free, runs the task,
        and returns the result. Kills and restarts only the worker
        that times out, leaving all others untouched.
        """
        worker = self._get_free_worker()
        try:
            return worker.run_task(fn, args, kwargs, timeout=timeout)
        except TimeoutError:
            with self._lock:
                worker.restart()
            raise

    def shutdown(self):
        """Shutdown all worker processes and clean up resources."""
        for w in self._workers:
            w.shutdown()
