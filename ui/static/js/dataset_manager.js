(function () {
  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok || !data.success) {
          throw new Error((data && data.error) || r.statusText || 'Request failed');
        }
        return data;
      });
    });
  }

  function showResult(el, data) {
    if (!el) return;
    el.textContent = JSON.stringify(data, null, 2);
  }

  function showError(el, err) {
    if (!el) return;
    el.textContent = 'Error: ' + (err && err.message ? err.message : String(err));
  }

  var splitResult = document.getElementById('splitResult');
  var btnSplit = document.getElementById('btnSplitRaw');
  if (btnSplit) {
    btnSplit.addEventListener('click', function () {
      var sourceEl = document.getElementById('splitSource');
      if (!sourceEl || !sourceEl.value) {
        showError(splitResult, new Error('No raw source selected'));
        return;
      }
      splitResult.textContent = 'Splitting...';
      postJson('/testset/api/split', {
        source: sourceEl.value,
        runner_id: document.getElementById('splitRunner').value,
        size: parseInt(document.getElementById('splitSize').value, 10) || 20,
        write_test_remain: document.getElementById('splitWriteRemain').checked,
      })
        .then(function (data) {
          showResult(splitResult, data.result);
          setTimeout(function () {
            var runner = document.getElementById('splitRunner').value;
            window.location.href = '/testset/?runner_id=' + encodeURIComponent(runner);
          }, 800);
        })
        .catch(function (err) { showError(splitResult, err); });
    });
  }

  var sampleResult = document.getElementById('sampleResult');
  var btnSample = document.getElementById('btnSampleCsv');
  if (btnSample) {
    btnSample.addEventListener('click', function () {
      var sourceEl = document.getElementById('sampleSource');
      if (!sourceEl || !sourceEl.value) {
        showError(sampleResult, new Error('No source test dataset selected'));
        return;
      }
      sampleResult.textContent = 'Sampling...';
      var payload = {
        runner_id: document.getElementById('sampleRunner').value,
        source: sourceEl.value,
        size: parseInt(document.getElementById('sampleSize').value, 10) || 5,
        seed: parseInt(document.getElementById('sampleSeed').value, 10) || 42,
      };
      var out = document.getElementById('sampleOutput').value.trim();
      if (out) payload.output = out;
      postJson('/testset/api/sample', payload)
        .then(function (data) {
          showResult(sampleResult, data.result);
          setTimeout(function () {
            var runner = document.getElementById('sampleRunner').value;
            window.location.href = '/testset/?runner_id=' + encodeURIComponent(runner);
          }, 800);
        })
        .catch(function (err) { showError(sampleResult, err); });
    });
  }
})();
