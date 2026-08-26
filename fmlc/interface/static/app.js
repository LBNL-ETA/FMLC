// Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
// The Regents of the University of California, through Lawrence Berkeley
// National Laboratory (subject to receipt of any required approvals
// from the U.S. Dept. of Energy). All rights reserved.
//
// Framework for Multi Layer Control
// Frontend logic for the FMLC web interface (vanilla JS, no external dependencies).

'use strict';

var POLL_INTERVAL_MS = 2000; // ms between UI status/log/module-log polls

var _configJson = null;    // parsed JSON from the selected file
var _loopStructure = [];   // loop descriptors from /api/load
var _pollTimer = null;     // setInterval handle
var _hydrated = false;     // true once loop structure has been restored from server

function showPage(name, link) {
  var pages = document.querySelectorAll('.page');
  for (var i = 0; i < pages.length; i++) { pages[i].classList.remove('active'); }
  var target = document.getElementById('page-' + name);
  if (target) { target.classList.add('active'); }

  var links = document.querySelectorAll('nav ul li a');
  for (var j = 0; j < links.length; j++) { links[j].classList.remove('active'); }
  if (link) { link.classList.add('active'); }
}

function onFileSelected(input) {
  var file = input.files && input.files[0];
  if (!file) { return; }
  showMsg('');

  var reader = new FileReader();
  reader.onload = function (evt) {
    try {
      _configJson = JSON.parse(evt.target.result);
      // Populate fields from stack_config; only overwrite if each key is present
      var sc = _configJson.stack_config || {};
      if ('tz' in sc) { document.getElementById('cfg-tz').value = sc['tz']; }
      if ('name' in sc) { document.getElementById('cfg-name').value = sc['name']; }
      if ('log_level' in sc) { document.getElementById('cfg-loglevel').value = sc['log_level']; }
      if ('align_ts' in sc) { document.getElementById('cfg-align').value = sc['align_ts']; }
      if ('log_clear_period' in sc) { document.getElementById('cfg-log-clear').value = sc['log_clear_period'] / 3600; }
      if ('log_dump_period' in sc) { document.getElementById('cfg-log-dump').value = sc['log_dump_period'] / 3600; }
      if ('log_path' in sc) { document.getElementById('cfg-log-path').value = sc['log_path']; }

      setStackConfigInputs(false); // enable
      document.getElementById('btn-load').disabled = false;
      showMsg('File parsed. Click "Load Config" to initialise the stack.', true);
    } catch (e) {
      _configJson = null;
      document.getElementById('btn-load').disabled = true;
      setStackConfigInputs(true); // disable
      showMsg('ERROR: Could not parse JSON:' + e.message);
    }
  };
  reader.readAsText(file);
}

function loadConfig() {
  if (!_configJson) { showMsg('No config file loaded.'); return; }
  setButtons(false, false, false, false);
  showMsg('Loading config:', true);

  // Merge UI field values into the config as stack_config before posting
  var payload = JSON.parse(JSON.stringify(_configJson)); // deep copy
  payload.stack_config = {
    tz: parseInt(document.getElementById('cfg-tz').value, 10),
    name: document.getElementById('cfg-name').value,
    log_level: parseInt(document.getElementById('cfg-loglevel').value, 10),
    align_ts: parseFloat(document.getElementById('cfg-align').value) || null,
    log_clear_period: parseInt(document.getElementById('cfg-log-clear').value, 10) * 3600,
    log_dump_period: parseInt(document.getElementById('cfg-log-dump').value, 10) * 3600,
    log_path: document.getElementById('cfg-log-path').value
  };

  apiPost('/api/load', payload, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      setButtons(!!_configJson, false, false, false);
      setBadge('error');
      return;
    }
    _loopStructure = data.loops || [];
    buildTables(_loopStructure);
    buildModlogDropdown(_loopStructure);
    buildDvDropdown(_loopStructure);
    // Reflect the confirmed stack_config back from the server
    var sc = data.stack_config;
    document.getElementById('cfg-tz').value = sc['tz'];
    document.getElementById('cfg-name').value = sc['name'];
    document.getElementById('cfg-loglevel').value = sc['log_level'];
    document.getElementById('cfg-align').value = sc['align_ts'] !== null ? sc['align_ts'] : '';
    document.getElementById('cfg-log-clear').value = sc['log_clear_period'] / 3600;
    document.getElementById('cfg-log-dump').value = sc['log_dump_period'] / 3600;
    document.getElementById('cfg-log-path').value = sc['log_path'];
    setBadge('loaded');
    showMsg('Config loaded. Click "Start FMLC" to begin.', true);
    document.getElementById('btn-load').disabled = false;
    document.getElementById('btn-start').disabled = false;
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-unload').disabled = false;
    setStackConfigInputs(true); // stack already created; changes have no effect
  });
}

function startFmlc() {
  showMsg('Starting FMLC:', true);
  setButtons(false, false, false, false);

  apiPost('/api/start', {}, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      document.getElementById('btn-start').disabled = false;
      setBadge('error');
      return;
    }
    setBadge('running');
    showMsg('FMLC is running.', true);
    document.getElementById('btn-load').disabled = true;
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled = false;
    document.getElementById('btn-unload').disabled = true;
    setStackConfigInputs(true); // lock while running
  });
}

function stopFmlc() {
  showMsg('Stopping FMLC:', true);
  setButtons(false, false, false, false);

  apiPost('/api/stop', {}, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      document.getElementById('btn-stop').disabled = false;
      setBadge('error');
      return;
    }
    setBadge('stopped');
    showMsg('FMLC stopped. Click "Start FMLC" to resume, or "Unload FMLC" to reset.', true);
    document.getElementById('btn-load').disabled = !(_configJson !== null);
    document.getElementById('btn-start').disabled = !(_loopStructure.length > 0 && _configJson !== null);
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-unload').disabled = false;
    setStackConfigInputs(true); // stack still in memory; changes have no effect
  });
}

function unloadFmlc() {
  showMsg('Unloading FMLC:', true);
  setButtons(false, false, false, false);

  apiPost('/api/unload', {}, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      document.getElementById('btn-unload').disabled = false;
      setBadge('error');
      return;
    }
    // Reset all client-side stack state
    _loopStructure = [];
    _hydrated = false;
    var container = document.getElementById('loop-tables');
    container.innerHTML = '<p style="color:#888; font-size:13px;">Load a config file to display the control loop tables.</p>';
    setStackConfigInputs(true); // disable until next config is loaded
    clearLogs();
    setBadge('idle');
    showMsg('FMLC unloaded. Select a config file and click "Load Config" to start fresh.', true);
    // Only Load Config can be re-enabled (if a file is already selected)
    document.getElementById('btn-load').disabled = (_configJson === null);
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-unload').disabled = true;
  });
}

function startPolling() {
  if (_pollTimer !== null) { return; }
  _pollTimer = setInterval(pollStatus, POLL_INTERVAL_MS);
}

function pollStatus() {
  apiGet('/api/status', function (data, err) {
    if (err || !data) { return; }
    var badge = document.getElementById('status-badge');
    if (badge && badge.textContent.toLowerCase() !== data.fmlc_status) {
      setBadge(data.fmlc_status);
    }

    // Hydrate loop structure from server on reload if not already done this session
    if (!_hydrated && data.loops && data.loops.length > 0) {
      _loopStructure = data.loops;
      buildTables(_loopStructure);
      buildModlogDropdown(_loopStructure);
      buildDvDropdown(_loopStructure);
      _hydrated = true;
    }

    syncButtonsFromStatus(data.fmlc_status);
    var modules = data.modules || {};
    for (var name in modules) {
      if (!modules.hasOwnProperty(name)) { continue; }
      var info = modules[name];
      updateCell('log-' + safeCellId(name), info.last_log || '');
      updateCell('exec-' + safeCellId(name), info.last_exec || '');
      updateCell('dur-' + safeCellId(name), (info.last_duration !== undefined && info.last_duration !== -1) ? info.last_duration + ' s' : '-');
    }
  });
  pollModuleLog();
  pollDvLastValues();
  pollDvAutoUpdate();
  apiGet('/api/logs', function (data, err) {
    if (err || !data) { return; }
    var lines = data.lines || [];
    // Last log line on main page
    var lastEl = document.getElementById('last-log');
    if (lastEl && lines.length) { lastEl.textContent = lines[lines.length - 1]; }
    // Full log on log tab
    var el = document.getElementById('log-output');
    if (!el) { return; }
    var text = lines.join('\n');
    if (el.textContent !== text) {
      var atBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 2;
      el.textContent = text;
      if (atBottom) { el.scrollTop = el.scrollHeight; } // auto-scroll only when at bottom
    }
  });
}

function clearLogs() {
  apiPost('/api/logs/clear', {}, function () {
    var el = document.getElementById('log-output');
    if (el) { el.textContent = ''; }
    var lastEl = document.getElementById('last-log');
    if (lastEl) { lastEl.textContent = ''; }
  });
}

function updateCell(cellId, newText) {
  var cell = document.getElementById(cellId);
  if (!cell) { return; }
  if (cell.textContent !== newText) {
    cell.textContent = newText;
  }
}

function syncButtonsFromStatus(status) {
  var btnLoad = document.getElementById('btn-load');
  var btnStart = document.getElementById('btn-start');
  var btnStop = document.getElementById('btn-stop');
  var btnUnload = document.getElementById('btn-unload');
  if (!btnLoad) { return; }

  // Load Config requires a file to have been parsed in this browser session.
  var hasFile = (_configJson !== null);
  // Start/Unload only require a stack to be present on the server (survives reload).
  var hasStack = (_loopStructure.length > 0);

  if (status === 'running') {
    btnLoad.disabled = true; // cannot load a new config while running
    btnStart.disabled = true;
    btnStop.disabled = false;
    btnUnload.disabled = true; // must stop before unloading
    setStackConfigInputs(true); // locked while running
  } else if (status === 'stopped' || status === 'loaded') {
    btnLoad.disabled = !hasFile;
    btnStart.disabled = !hasStack;
    btnStop.disabled = true;
    btnUnload.disabled = !hasStack;
    setStackConfigInputs(true); // stack exists; changes have no effect until next Load Config
  } else {
    // idle or error: editable whenever a file has been selected
    btnLoad.disabled = !hasFile;
    btnStart.disabled = true;
    btnStop.disabled = true;
    btnUnload.disabled = true;
    setStackConfigInputs(!hasFile);
  }
}

function buildTables(loops) {
  var container = document.getElementById('loop-tables');
  container.innerHTML = '';

  if (!loops || loops.length === 0) {
    container.innerHTML = '<p style="color:#888;font-size:13px;">No loops found in config.</p>';
    return;
  }

  for (var i = 0; i < loops.length; i++) {
    var loop = loops[i];
    var section = document.createElement('div');
    section.className = 'panel';

    var heading = document.createElement('h2');
    heading.textContent = 'Loop: ' + loop.name + ' (' + loop.sampletime + ' s)';
    section.appendChild(heading);

    var table = document.createElement('table');

    // Header row
    var thead = table.createTHead();
    var hrow = thead.insertRow();
    ['Module', 'Last Log Message', 'Last Execution Time', 'Duration'].forEach(function (col) {
      var th = document.createElement('th');
      th.textContent = col;
      hrow.appendChild(th);
    });

    // Data rows - one per module in this loop
    var tbody = table.createTBody();
    var mods = loop.modules || [];
    for (var j = 0; j < mods.length; j++) {
      var modName = mods[j];
      var row = tbody.insertRow();

      var tdName = row.insertCell();
      tdName.textContent = modName;

      var tdLog = row.insertCell();
      tdLog.id = 'log-' + safeCellId(modName);
      tdLog.className = 'cell-log';
      tdLog.textContent = '-';

      var tdExec = row.insertCell();
      tdExec.id = 'exec-' + safeCellId(modName);
      tdExec.className = 'cell-exec';
      tdExec.textContent = '-';

      var tdDur = row.insertCell();
      tdDur.id = 'dur-' + safeCellId(modName);
      tdDur.className = 'cell-exec';
      tdDur.textContent = '-';
    }

    section.appendChild(table);
    container.appendChild(section);
  }
}

function safeCellId(name) {
  return name.replace(/[^a-zA-Z0-9_-]/g, '_');
}

// Enable or disable all stack config input fields.
function setStackConfigInputs(disabled) {
  document.getElementById('cfg-tz').disabled = disabled;
  document.getElementById('cfg-name').disabled = disabled;
  document.getElementById('cfg-loglevel').disabled = disabled;
  document.getElementById('cfg-align').disabled = disabled;
  document.getElementById('cfg-log-clear').disabled = disabled;
  document.getElementById('cfg-log-dump').disabled = disabled;
  document.getElementById('cfg-log-path').disabled = disabled;
}

function setButtons(load, start, stop, unload) {
  document.getElementById('btn-load').disabled = !load;
  document.getElementById('btn-start').disabled = !start;
  document.getElementById('btn-stop').disabled = !stop;
  document.getElementById('btn-unload').disabled = !unload;
}

function setBadge(status) {
  var badge = document.getElementById('status-badge');
  if (!badge) { return; }
  badge.className = status || 'idle';
  badge.textContent = status ? (status.charAt(0).toUpperCase() + status.slice(1)) : 'Idle';
}

function showMsg(text, ok) {
  var el = document.getElementById('msg-line');
  if (!el) { return; }
  el.textContent = text || '';
  el.className = ok ? 'ok' : '';
}

function apiPost(url, payload, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', url, true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.onreadystatechange = function () {
    if (xhr.readyState !== 4) { return; }
    try {
      callback(JSON.parse(xhr.responseText), xhr.status >= 400 ? ('HTTP ' + xhr.status) : null);
    } catch (e) { callback(null, 'Parse error: ' + e.message); }
  };
  xhr.onerror = function () { callback(null, 'Network error'); };
  xhr.send(JSON.stringify(payload));
}

function apiGet(url, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.onreadystatechange = function () {
    if (xhr.readyState !== 4) { return; }
    try {
      callback(JSON.parse(xhr.responseText), xhr.status >= 400 ? ('HTTP ' + xhr.status) : null);
    } catch (e) { callback(null, 'Parse error: ' + e.message); }
  };
  xhr.onerror = function () { callback(null, 'Network error'); };
  xhr.send();
}

// ---- Module Log tab ----

function getTruncLen() {
  var el = document.getElementById('modlog-trunc');
  var v = el ? parseInt(el.value, 10) : 120;
  return (isNaN(v) || v < 1) ? 120 : v;
}

function buildModlogDropdown(loops) {
  var sel = document.getElementById('modlog-selector');
  sel.innerHTML = '<option value="">Select Controller</option>';
  for (var i = 0; i < loops.length; i++) {
    var mods = loops[i].modules || [];
    for (var j = 0; j < mods.length; j++) {
      var opt = document.createElement('option');
      opt.value = mods[j];
      opt.textContent = mods[j];
      sel.appendChild(opt);
    }
  }
  clearModlogPanels();
}

function onModlogSelect() {
  var name = document.getElementById('modlog-selector').value;
  if (!name) { clearModlogPanels(); return; }
  fetchModuleLog(name);
}

function fetchModuleLog(name) {
  apiGet('/api/module_log?name=' + encodeURIComponent(name), function (data, err) {
    if (err || !data || data.status !== 'ok') { clearModlogPanels(); return; }
    renderModlog(data.data);
  });
}

function clearModlogPanels() {
  var empty = '<tr><td colspan="2" style="color:#aaa;">—</td></tr>';
  document.getElementById('modlog-inputs-body').innerHTML = empty;
  document.getElementById('modlog-outputs-body').innerHTML = empty;
  document.getElementById('modlog-log-val').textContent = '—';
  document.getElementById('modlog-exec-val').textContent = '—';
  document.getElementById('modlog-dur-val').textContent = '—';
}

function renderModlog(data) {
  renderKVTable('modlog-inputs-body', data.inputs || {});
  renderKVTable('modlog-outputs-body', data.outputs || {});
  document.getElementById('modlog-log-val').textContent = data.log || '—';
  document.getElementById('modlog-exec-val').textContent = data.last_exec || '—';
  var dur = data.last_duration;
  document.getElementById('modlog-dur-val').textContent =
    (dur !== undefined && dur !== -1) ? dur + ' s' : '—';
}

function makeTruncCell(valStr) {
  var td = document.createElement('td');
  td.className = 'cell-val';
  var truncLen = getTruncLen();
  if (valStr.length > truncLen) {
    var trunc = document.createElement('span');
    trunc.className = 'modlog-val-trunc';
    trunc.textContent = valStr.slice(0, truncLen) + '…';

    var full = document.createElement('span');
    full.className = 'modlog-val-full';
    full.textContent = valStr;

    var toggle = document.createElement('span');
    toggle.className = 'modlog-toggle';
    toggle.textContent = '[show more]';
    (function (tr, fu, tg) {
      tg.onclick = function () {
        if (!fu.style.display || fu.style.display === 'none') {
          tr.style.display = 'none';
          fu.style.display = 'inline';
          tg.textContent = '[show less]';
        } else {
          fu.style.display = 'none';
          tr.style.display = 'inline';
          tg.textContent = '[show more]';
        }
      };
    }(trunc, full, toggle));

    td.appendChild(trunc);
    td.appendChild(full);
    td.appendChild(toggle);
  } else {
    td.textContent = valStr;
  }
  return td;
}

function renderKVTable(tbodyId, kvObj) {
  var tbody = document.getElementById(tbodyId);
  var keys = Object.keys(kvObj);
  if (!keys.length) {
    tbody.innerHTML = '<tr><td colspan="2" style="color:#aaa;">—</td></tr>';
    return;
  }

  // Rebuild only when the key set changes (different number of rows or different names)
  var rows = tbody.rows;
  var needsRebuild = (rows.length !== keys.length);
  if (!needsRebuild) {
    for (var i = 0; i < keys.length; i++) {
      if (!rows[i] || rows[i].cells[0].textContent !== keys[i]) { needsRebuild = true; break; }
    }
  }
  if (needsRebuild) {
    tbody.innerHTML = '';
    for (var j = 0; j < keys.length; j++) {
      var row = tbody.insertRow();
      row.insertCell().textContent = keys[j];
      var raw = kvObj[keys[j]];
      var valStr = (raw === null || raw === undefined) ? 'null' : String(raw);
      row.appendChild(makeTruncCell(valStr));
    }
    return;
  }

  // Key set unchanged: update only cells whose value has changed, preserving expanded state
  for (var k = 0; k < keys.length; k++) {
    var rawVal = kvObj[keys[k]];
    var newStr = (rawVal === null || rawVal === undefined) ? 'null' : String(rawVal);
    var cell = rows[k].cells[1];
    // Read current displayed value from whichever span is active (or plain text)
    var fullSpan = cell.querySelector('.modlog-val-full');
    var truncSpan = cell.querySelector('.modlog-val-trunc');
    var currentStr = fullSpan ? fullSpan.textContent : (truncSpan ? (truncSpan.textContent.slice(0, -1)) : cell.textContent);
    if (currentStr === newStr) { continue; } // nothing changed, leave DOM intact
    // Value changed: replace the cell content, reset to truncated view
    var newCell = makeTruncCell(newStr);
    rows[k].replaceChild(newCell, cell);
  }
}

// Only fetch when Module Log tab is active and a controller is selected
function pollModuleLog() {
  var page = document.getElementById('page-modlog');
  if (!page || !page.classList.contains('active')) { return; }
  var name = document.getElementById('modlog-selector').value;
  if (name) { fetchModuleLog(name); }
}

// Update Last Value cells in Data Viewer tables without rebuilding rows (preserves checkboxes)
function dvUpdateLastValues(tbodyId, kvObj, prefix) {
  var tbody = document.getElementById(tbodyId);
  var rows = tbody.rows;
  for (var i = 0; i < rows.length; i++) {
    var nameCell = rows[i].cells[1];
    if (!nameCell) { continue; }
    var k = nameCell.textContent;
    if (!(k in kvObj)) { continue; }
    var raw = kvObj[k];
    var newStr = (raw === null || raw === undefined) ? 'null' : String(raw);
    var valCell = rows[i].cells[2];
    if (!valCell) { continue; }
    // Read current full value from span or plain text
    var fullSpan = valCell.querySelector('.modlog-val-full');
    var currentStr = fullSpan ? fullSpan.textContent : valCell.textContent.replace(/…$/, '');
    if (currentStr === newStr) { continue; }
    // Value changed: rebuild cell (truncated), preserving checkbox in cell 0
    var newCell = document.createElement('td');
    newCell.className = 'cell-val';
    newCell.textContent = newStr.length > 80 ? newStr.slice(0, 80) + '…' : newStr;
    rows[i].replaceChild(newCell, valCell);
  }
}

// Refresh Data Viewer last values when the tab is active and a controller is selected
function pollDvLastValues() {
  var page = document.getElementById('page-dataviewer');
  if (!page || !page.classList.contains('active')) { return; }
  var name = document.getElementById('dv-selector').value;
  if (!name) { return; }
  apiGet('/api/module_log?name=' + encodeURIComponent(name), function (data, err) {
    if (err || !data || data.status !== 'ok') { return; }
    dvUpdateLastValues('dv-inputs-body', data.data.inputs || {}, 'input.');
    dvUpdateLastValues('dv-outputs-body', data.data.outputs || {}, 'output.');
  });
}

// ---- Data Viewer tab ----

var _dvLastCsvUrl = null; // URL of the last gathered flat CSV
var _dvGathering = false; // prevent overlapping auto-update calls

function buildDvDropdown(loops) {
  var sel = document.getElementById('dv-selector');
  sel.innerHTML = '<option value="">Select Controller</option>';
  for (var i = 0; i < loops.length; i++) {
    var mods = loops[i].modules || [];
    for (var j = 0; j < mods.length; j++) {
      var opt = document.createElement('option');
      opt.value = mods[j];
      opt.textContent = mods[j];
      sel.appendChild(opt);
    }
  }
  dvClearPanels();
  document.getElementById('dv-btn-open').disabled = true;
}

function onDvSelect() {
  var name = document.getElementById('dv-selector').value;
  dvClearPanels();
  document.getElementById('dv-btn-open').disabled = true;
  _dvLastCsvUrl = null;
  if (!name) { dvSetStatus(''); return; }
  apiGet('/api/module_log?name=' + encodeURIComponent(name), function (data, err) {
    if (err || !data || data.status !== 'ok') { dvSetStatus('Failed to load outputs.'); return; }
    dvRenderKvTable('dv-inputs-body', data.data.inputs || {}, 'input.');
    dvRenderKvTable('dv-outputs-body', data.data.outputs || {}, 'output.');
    document.getElementById('dv-btn-open').disabled = false;
  });
}

function dvClearPanels() {
  var empty = '<tr><td colspan="3" style="color:#aaa;">—</td></tr>';
  document.getElementById('dv-inputs-body').innerHTML = empty;
  document.getElementById('dv-outputs-body').innerHTML = empty;
}

function dvSetStatus(msg) {
  document.getElementById('dv-status').textContent = msg;
}

function dvClassifyValue(raw) {
  // Returns 'scalar', 'flat_json', 'df_json', or 'string'
  if (raw === null || raw === undefined) { return 'scalar'; }
  var n = Number(raw);
  if (!isNaN(n) && String(raw) !== '') { return 'scalar'; }
  var s = String(raw);
  if (s.startsWith('{') || s.startsWith('[')) {
    try {
      var parsed = JSON.parse(s);
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        if ('columns' in parsed || 'index' in parsed) { return 'df_json'; }
        return 'flat_json';
      }
    } catch (e) { /* not valid JSON */ }
  }
  return 'string';
}

function dvRenderKvTable(tbodyId, kvObj, prefix) {
  var tbody = document.getElementById(tbodyId);
  tbody.innerHTML = '';
  var keys = Object.keys(kvObj);
  if (!keys.length) {
    tbody.innerHTML = '<tr><td colspan="3" style="color:#aaa;">—</td></tr>';
    return;
  }
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    var raw = kvObj[k];
    var valStr = (raw === null || raw === undefined) ? 'null' : String(raw);
    var kind = dvClassifyValue(raw);

    var tr = document.createElement('tr');
    var tdCb = document.createElement('td');
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'dv-output-cb';
    cb.value = prefix + k;   // prefixed key sent to server

    if (kind === 'string') {
      cb.checked = false;
      cb.disabled = true;
      tr.style.color = '#aaa';
    } else if (kind === 'df_json') {
      cb.checked = false;
    } else {
      cb.checked = true;
    }

    tdCb.appendChild(cb);
    var tdName = document.createElement('td');
    tdName.textContent = k;
    var tdVal = document.createElement('td');
    tdVal.className = 'cell-val';
    tdVal.textContent = valStr.length > 80 ? valStr.slice(0, 80) + '…' : valStr;
    tr.appendChild(tdCb);
    tr.appendChild(tdName);
    tr.appendChild(tdVal);
    tbody.appendChild(tr);
  }
}

function dvSelectedKeys() {
  var cbs = document.querySelectorAll('.dv-output-cb');
  var keys = [];
  for (var i = 0; i < cbs.length; i++) {
    if (cbs[i].checked) { keys.push(cbs[i].value); }
  }
  return keys;
}

function dvDatetimeToIso(inputId) {
  var val = document.getElementById(inputId).value;
  return val ? val.replace('T', ' ') : null;
}

function dvBuildPayload() {
  var name = document.getElementById('dv-selector').value;
  if (!name) { return null; }
  var keys = dvSelectedKeys();
  if (!keys.length) { return null; }
  return {
    module: name,
    keys: keys,
    start: dvDatetimeToIso('dv-start'),
    end: dvDatetimeToIso('dv-end')
  };
}

function dvDoGather(payload, callback) {
  if (_dvGathering) { return; }
  _dvGathering = true;
  apiPost('/api/data_outputs', payload, function (data, err) {
    _dvGathering = false;
    if (err || !data || data.status !== 'ok') {
      dvSetStatus('Error: ' + (data && data.message ? data.message : err));
      if (callback) { callback(false); }
      return;
    }
    var flat = data.flat_rows;
    var dfCount = data.df_count;
    var msg = 'Flat rows: ' + flat + '.';
    if (dfCount) { msg += ' DataFrame entries: ' + dfCount + '.'; }
    dvSetStatus(msg);
    var name = payload.module;
    var keys = payload.keys;
    _dvLastCsvUrl = '/api/data_csv?module=' + encodeURIComponent(name) +
      '&keys=' + encodeURIComponent(keys.join(',')) +
      (payload.start ? '&start=' + encodeURIComponent(payload.start) : '') +
      (payload.end ? '&end=' + encodeURIComponent(payload.end) : '');
    if (callback) { callback(flat > 0); }
  });
}

function gatherAndOpen() {
  var payload = dvBuildPayload();
  if (!payload) { dvSetStatus('Select a controller and at least one output.'); return; }
  dvSetStatus('Gathering…');
  document.getElementById('dv-btn-open').disabled = true;
  dvDoGather(payload, function (hasData) {
    document.getElementById('dv-btn-open').disabled = false;
    if (hasData) {
      var modName = document.getElementById('dv-selector').value;
      var url = '/static/dataviewer.html?autoreload=1' +
        '&title=' + encodeURIComponent(modName) +
        '&file=' + encodeURIComponent(_dvLastCsvUrl);
      window.open(url, '_blank');
    }
  });
}

// Called each poll cycle; silently re-gathers if Auto-Update is checked and a controller is selected
function pollDvAutoUpdate() {
  if (!document.getElementById('dv-auto-update').checked) { return; }
  var payload = dvBuildPayload();
  if (!payload) { return; }
  dvDoGather(payload, null);
}

startPolling();
