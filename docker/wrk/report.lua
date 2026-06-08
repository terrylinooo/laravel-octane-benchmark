-- wrk reporter: emits one machine-readable JSON line (prefixed __WRKJSON__) so
-- the harness can capture latency percentiles + error counts per cell.
-- wrk latency values are in microseconds; summary.duration is in microseconds.

done = function(summary, latency, requests)
  local dur_s = summary.duration / 1e6
  local rps = (dur_s > 0) and (summary.requests / dur_s) or 0
  local bucket_limits_us = {
    10000, 25000, 50000, 100000, 250000, 500000,
    1000000, 1250000, 1500000, 2000000
  }
  local bucket_counts = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }

  -- latency(i) returns one observed latency value and its exact request count.
  -- Aggregate only after the run, so histogram export adds no per-request Lua work.
  for i = 1, #latency do
    local value, count = latency(i)
    local bucket = #bucket_limits_us + 1
    for j, limit in ipairs(bucket_limits_us) do
      if value <= limit then
        bucket = j
        break
      end
    end
    bucket_counts[bucket] = bucket_counts[bucket] + count
  end

  local line = string.format(
    '__WRKJSON__{"requests":%d,"duration_s":%.3f,"bytes":%d,"rps":%.2f,' ..
    '"errors":{"connect":%d,"read":%d,"write":%d,"status":%d,"timeout":%d},' ..
    '"latency_histogram":{"corrected":true,' ..
    '"bounds_ms":[10,25,50,100,250,500,1000,1250,1500,2000],' ..
    '"counts":[%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d]},' ..
    '"latency_ms":{"min":%.3f,"max":%.3f,"mean":%.3f,"stdev":%.3f,' ..
    '"p50":%.3f,"p75":%.3f,"p90":%.3f,"p95":%.3f,"p99":%.3f,"p99_9":%.3f}}',
    summary.requests, dur_s, summary.bytes, rps,
    summary.errors.connect, summary.errors.read, summary.errors.write,
    summary.errors.status, summary.errors.timeout,
    bucket_counts[1], bucket_counts[2], bucket_counts[3], bucket_counts[4],
    bucket_counts[5], bucket_counts[6], bucket_counts[7], bucket_counts[8],
    bucket_counts[9], bucket_counts[10], bucket_counts[11],
    latency.min / 1000, latency.max / 1000, latency.mean / 1000, latency.stdev / 1000,
    latency:percentile(50) / 1000, latency:percentile(75) / 1000,
    latency:percentile(90) / 1000, latency:percentile(95) / 1000,
    latency:percentile(99) / 1000,
    latency:percentile(99.9) / 1000
  )
  io.write(line .. "\n")
end
