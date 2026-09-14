import { performance } from "node:perf_hooks";

const baseUrl = process.argv[2] || "http://127.0.0.1:8001";
const users = Number(process.argv[3] || 12);
const rounds = Number(process.argv[4] || 8);
const paths = ["/", "/series/", "/accounts/pass_login/"];
const samples = [];

async function request(pathname) {
  const started = performance.now();
  try {
    const response = await fetch(`${baseUrl}${pathname}`, {
      redirect: "manual",
      headers: { "User-Agent": "EgoFit-performance-probe/1.0" },
    });
    const body = await response.arrayBuffer();
    samples.push({
      path: pathname,
      status: response.status,
      ms: performance.now() - started,
      bytes: body.byteLength,
      error: null,
    });
  } catch (error) {
    samples.push({
      path: pathname,
      status: 0,
      ms: performance.now() - started,
      bytes: 0,
      error: error.message,
    });
  }
}

async function virtualUser() {
  for (let round = 0; round < rounds; round += 1) {
    await Promise.all(paths.map(request));
  }
}

const started = performance.now();
await Promise.all(Array.from({ length: users }, virtualUser));
const elapsed = performance.now() - started;

function percentile(values, percentileValue) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil((percentileValue / 100) * sorted.length) - 1);
  return sorted[Math.max(0, index)];
}

const byPath = Object.fromEntries(paths.map((pathname) => {
  const pathSamples = samples.filter((sample) => sample.path === pathname);
  const timings = pathSamples.map((sample) => sample.ms);
  const failures = pathSamples.filter((sample) => sample.status >= 500 || sample.error);
  return [pathname, {
    requests: pathSamples.length,
    failures: failures.length,
    p50_ms: Number(percentile(timings, 50).toFixed(1)),
    p95_ms: Number(percentile(timings, 95).toFixed(1)),
    max_ms: Number(Math.max(...timings, 0).toFixed(1)),
    statuses: Object.fromEntries([...new Set(pathSamples.map((sample) => sample.status))].map((status) => [status, pathSamples.filter((sample) => sample.status === status).length])),
    errors: Object.fromEntries([...new Set(failures.map((sample) => sample.error || `HTTP ${sample.status}`))].map((error) => [error, failures.filter((sample) => (sample.error || `HTTP ${sample.status}`) === error).length])),
    average_bytes: Math.round(pathSamples.reduce((sum, sample) => sum + sample.bytes, 0) / Math.max(pathSamples.length, 1)),
  }];
}));

console.log(JSON.stringify({
  baseUrl,
  users,
  rounds,
  total_requests: samples.length,
  total_failures: samples.filter((sample) => sample.status >= 500 || sample.error).length,
  elapsed_ms: Number(elapsed.toFixed(1)),
  requests_per_second: Number((samples.length / (elapsed / 1000)).toFixed(2)),
  by_path: byPath,
}, null, 2));
