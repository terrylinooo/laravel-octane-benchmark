-- wrk reporter: emits one machine-readable JSON line (prefixed __WRKJSON__) so
-- the harness can capture latency percentiles + error counts per cell.
-- wrk latency values are in microseconds; summary.duration is in microseconds.

done = function(summary, latency, requests)
  local dur_s = summary.duration / 1e6
  local rps = (dur_s > 0) and (summary.requests / dur_s) or 0

  local line = string.format(
    '__WRKJSON__{"requests":%d,"duration_s":%.3f,"bytes":%d,"rps":%.2f,' ..
    '"errors":{"connect":%d,"read":%d,"write":%d,"status":%d,"timeout":%d},' ..
    '"latency_ms":{"min":%.3f,"max":%.3f,"mean":%.3f,"stdev":%.3f,' ..
    '"p50":%.3f,"p75":%.3f,"p90":%.3f,"p95":%.3f,"p99":%.3f,"p99_9":%.3f}}',
    summary.requests, dur_s, summary.bytes, rps,
    summary.errors.connect, summary.errors.read, summary.errors.write,
    summary.errors.status, summary.errors.timeout,
    latency.min / 1000, latency.max / 1000, latency.mean / 1000, latency.stdev / 1000,
    latency:percentile(50) / 1000, latency:percentile(75) / 1000,
    latency:percentile(90) / 1000, latency:percentile(95) / 1000,
    latency:percentile(99) / 1000,
    latency:percentile(99.9) / 1000
  )
  io.write(line .. "\n")
end
