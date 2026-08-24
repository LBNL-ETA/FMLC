#!/usr/bin/env python3
# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Flask backend server for the FMLC web interface.
"""

# pylint: disable=invalid-name, broad-except

from __future__ import annotations

import argparse
import datetime as dtm
import importlib
import logging
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from fmlc.stackedclasses import controller_stack

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / 'static'
app = Flask(__name__, static_folder=str(STATIC_DIR))
log = logging.getLogger(__name__)

_lock = threading.Lock()
_stack: controller_stack | None = None
_loop_structure: list | None = None
_running = False
_fmlc_status = 'idle'
_bg_thread: threading.Thread | None = None
_LOOP_TIMESTEP = 0.5 # seconds between query_control calls

def _fmlc_loop() -> None:
    """Daemon thread: calls query_control() every _LOOP_TIMESTEP seconds while _running."""
    log.info('FMLC background loop started.')
    while _running:
        try:
            with _lock:
                s = _stack
            if s is not None:
                s.query_control(time.time())
        except Exception as exc:
            log.warning('Error in FMLC loop: %s', exc)
        time.sleep(_LOOP_TIMESTEP)
    log.info('FMLC background loop stopped.')

def _stop_loop() -> None:
    """Stop the background loop and wait for the thread to exit."""
    global _running, _bg_thread  # pylint: disable=global-statement
    _running = False
    if _bg_thread is not None and _bg_thread.is_alive():
        _bg_thread.join(timeout=_LOOP_TIMESTEP * 10)
    _bg_thread = None

def _start_loop() -> None:
    """Start the background loop thread; no-op if already running."""
    global _running, _bg_thread  # pylint: disable=global-statement
    if _running and _bg_thread is not None and _bg_thread.is_alive():
        return
    _running = True
    _bg_thread = threading.Thread(target=_fmlc_loop, daemon=True, name='fmlc-loop')
    _bg_thread.start()

def _module_status(stack: controller_stack) -> dict:
    """Return per-module last log message and last execution time, read from PythonDB."""
    stack.read_from_db()
    db = stack.data_db

    result = {}
    for name in stack.controller:
        # Log message: stored as string; init value is 'Initialize FMLC.'
        last_log = db[name + '_logfmlc'] if name + '_logfmlc' in db else ''
        if isinstance(last_log, list):
            last_log = last_log[0] if last_log else ''
        last_log = str(last_log)

        # Last execution: Unix timestamp float, 0 means never run
        last_ts = db[name + '_lastfmlc'] if name + '_lastfmlc' in db else 0
        try:
            last_ts = float(last_ts)
        except (TypeError, ValueError):
            last_ts = 0
        last_exec = (dtm.datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M:%S')
                     if last_ts else 'Never')

        result[name] = {'last_log': last_log, 'last_exec': last_exec}
    return result

def _resolve_config(config: dict) -> tuple:
    """Parse a JSON config dict and return (controller, mapping) ready for controller_stack."""
    if 'controller' not in config or not config['controller']:
        raise ValueError("Config must contain a non-empty 'controller' dict.")
    if 'mapping' not in config or not isinstance(config['mapping'], dict):
        raise ValueError("Config must contain a 'mapping' dict.")

    raw_controller = config['controller']
    mapping = config['mapping']
    controller = {}
    for name, entry in raw_controller.items():
        fn_path = entry['function']
        try:
            module_path, class_name = fn_path.rsplit('.', 1)
            cls = getattr(importlib.import_module(module_path), class_name)
        except (ValueError, ModuleNotFoundError, AttributeError) as exc:
            raise ValueError(
                f"Cannot import '{fn_path}' for controller '{name}': {exc}"
            ) from exc
        controller[name] = {
            'function': cls,
            'sampletime': entry['sampletime'],
        }
        if 'parameter' in entry:
            controller[name]['parameter'] = entry['parameter']

    return controller, mapping

def _build_loop_structure(stack: controller_stack) -> list:
    """Convert stack.execution_list into a JSON-serialisable list of loop descriptors."""
    loops = []
    for task in stack.execution_list:
        root_name = task['controller'][0]
        st = stack.controller[root_name]['sampletime']
        loops.append({
            'name': root_name,
            'sampletime': st,
            'modules': list(task['controller']),
        })
    return loops

@app.route('/')
def index():
    """Serve the single-page UI."""
    return send_from_directory(str(STATIC_DIR), 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve any file from the static/ directory under the /static/ prefix."""
    return send_from_directory(str(STATIC_DIR), filename)

@app.route('/api/load', methods=['POST'])
def api_load():
    """Load a FMLC JSON config and initialise the controller_stack."""
    global _stack, _loop_structure, _fmlc_status  # pylint: disable=global-statement

    try:
        config = request.get_json(force=True)
        if config is None:
            return jsonify({'status': 'error', 'message': 'No JSON body received.'}), 400
        # Strip comment keys beginning with '_' (used in example_config.json)
        config = {k: v for k, v in config.items() if not k.startswith('_')}
        controller, mapping = _resolve_config(config)
    except (ValueError, KeyError) as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 400

    # Auto-stop any running loop before replacing the stack
    with _lock:
        was_running = _running
    if was_running:
        _stop_loop()

    # Shut down the existing stack cleanly
    with _lock:
        old_stack = _stack
        _stack = None
        _loop_structure = None
        _fmlc_status = 'idle'

    if old_stack is not None:
        try:
            old_stack.shutdown()
        except Exception as exc:
            log.warning('Error shutting down old stack: %s', exc)

    # Build the new stack
    try:
        new_stack = controller_stack(
            controller,
            mapping,
            parallel=True,
            timestep=_LOOP_TIMESTEP,
            name='FMLCWebUI',
        )
    except Exception as exc:
        _fmlc_status = 'error'
        return jsonify({
            'status': 'error',
            'message': f'Failed to initialise stack: {exc}'
        }), 500

    loops = _build_loop_structure(new_stack)

    with _lock:
        _stack = new_stack
        _loop_structure = loops
        _fmlc_status = 'loaded'

    return jsonify({'status': 'ok', 'loops': loops})

@app.route('/api/start', methods=['POST'])
def api_start():
    """Start or resume the FMLC background control loop."""
    global _fmlc_status  # pylint: disable=global-statement

    with _lock:
        s = _stack

    if s is None:
        return jsonify({
            'status': 'error',
            'message': 'No config loaded. Call /api/load first.'
        }), 400

    _start_loop()

    with _lock:
        _fmlc_status = 'running'

    return jsonify({'status': 'ok', 'fmlc_status': 'running'})

@app.route('/api/unload', methods=['POST'])
def api_unload():
    """Stop the loop and fully shut down the stack, resetting state to idle."""
    global _stack, _loop_structure, _fmlc_status  # pylint: disable=global-statement

    _stop_loop()

    with _lock:
        old_stack = _stack
        _stack = None
        _loop_structure = None
        _fmlc_status = 'idle'

    if old_stack is not None:
        def _do_shutdown():
            try:
                old_stack.shutdown()
            except Exception as exc:
                log.warning('Error during unload shutdown: %s', exc)

        t = threading.Thread(target=_do_shutdown, daemon=True)
        t.start()
        t.join(timeout=10) # wait up to 10 s; abandon if still blocked
        if t.is_alive():
            log.warning('Stack shutdown timed out after 10 s - abandoned.')

    return jsonify({'status': 'ok', 'fmlc_status': 'idle'})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Pause the FMLC background loop; stack stays in memory for resume."""
    global _fmlc_status  # pylint: disable=global-statement

    with _lock:
        s = _stack

    if s is None:
        return jsonify({'status': 'error', 'message': 'No stack loaded.'}), 400

    _stop_loop()

    with _lock:
        _fmlc_status = 'stopped'

    return jsonify({'status': 'ok', 'fmlc_status': 'stopped'})

@app.route('/api/status', methods=['GET'])
def api_status():
    """Return current FMLC status and per-module log/exec information."""
    with _lock:
        s = _stack
        status = _fmlc_status

    modules = {}
    if s is not None:
        try:
            modules = _module_status(s)
        except Exception as exc:
            log.warning('Error reading module status: %s', exc)

    return jsonify({'fmlc_status': status, 'modules': modules})

def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='FMLC Web Interface server.')
    parser.add_argument('--host', default='127.0.0.1',
                        help='Host/interface to bind (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000,
                        help='Port to listen on (default: 5000)')
    parser.add_argument('--no-browser', action='store_true',
                        help='Do not automatically open a browser tab.')
    return parser.parse_args()

def main() -> None:
    """Entry point. Usage: server.py [--host 127.0.0.1] [--port 5000] [--no-browser]
    State: IDLE -> [Load] -> LOADED -> [Start] -> RUNNING -> [Stop] -> STOPPED
    """
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    url = f'http://{args.host}:{args.port}/'
    print(f'FMLC Web Interface running at {url}')
    print('Press Ctrl+C to stop.')

    if not args.no_browser:
        def _open_browser():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open_browser, daemon=True).start()

    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
