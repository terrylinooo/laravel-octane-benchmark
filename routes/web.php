<?php

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('welcome');
});

// Inspection endpoint: shows which server / worker handled the request.
// NOTE: worker_pid makes the response length vary, which makes `ab` report
// false "failed (length)" requests — use the /bench/* routes for load tests.
Route::get('/ping', function () {
    return response()->json([
        'pong' => true,
        'server' => env('OCTANE_SERVER', 'unknown'),
        'worker_pid' => getmypid(),
    ]);
});

/*
|--------------------------------------------------------------------------
| Benchmark workloads
|--------------------------------------------------------------------------
| Four routes that isolate one cost each, so the harness can show WHERE each
| Octane server wins. All are stateless (SESSION_DRIVER=array) so nothing
| serializes on shared writable state. Keep these minimal and deterministic.
*/

// Back-compat alias for the old fixed-length endpoint.
Route::get('/bench', fn () => response('OK'));

// hello — pure routing + response overhead. Fixed-length body.
Route::get('/bench/hello', fn () => response('OK'));

// json — serialization cost (cpu group). A tight json_encode + json_decode round-trip over
// a 1000-element integer array, looped BENCH_JSON_ITERATIONS times so the codec
// (not routing/middleware) dominates the response time — exactly what isolates
// serialization. Pure integers, so this measures raw codec throughput (no string
// escaping / unicode cost). Deterministic: the checksum (total encoded bytes) is
// identical on every server, so a miscompute or a silently-empty loop is visible.
// Default ~150 iters ≈ ~20ms — heavy enough to dominate routing, light enough that
// a concurrency sweep to 128 doesn't saturate into timeouts on a 4-core box.
Route::get('/bench/json', function () {
    $iterations = (int) env('BENCH_JSON_ITERATIONS', 150);
    $data = ['users' => range(1, 1000)];
    $checksum = 0;

    for ($i = 0; $i < $iterations; $i++) {
        $json = json_encode($data);
        $checksum += strlen($json);
        json_decode($json, true);
    }

    return response()->json(['iterations' => $iterations, 'checksum' => $checksum]);
});

// hash — integer/bitwise CPU work (cpu group). Deterministic sha256 chaining,
// identical bytes of work on every server. BENCH_HASH_ITERATIONS is the
// calibration knob: tune so this latency clearly dominates /bench/hello
// (target ~5-10x) on the bench host.
Route::get('/bench/hash', function () {
    $iterations = (int) env('BENCH_HASH_ITERATIONS', 2000);
    $hash = 'octane-benchmark-seed';
    for ($i = 0; $i < $iterations; $i++) {
        $hash = hash('sha256', $hash);
    }

    return response()->json(['iterations' => $iterations, 'digest' => substr($hash, 0, 16)]);
});

// mandelbrot — float/FPU-bound CPU work (cpu group). Escape-time Mandelbrot over a
// (2*DIM)x(2*DIM) grid, up to MAX_ITER iterations/cell. Complements /bench/hash,
// which is integer/bitwise (sha256): this stresses the floating-point path instead,
// so the two can disagree on which server wins. Deterministic — the checksum (sum of
// per-cell iteration counts) is identical on every server, so a miscompute is visible.
// Calibration: DIM (grid) and MAX_ITER (escape cap) size one pass; REPEAT scales up.
// Defaults DIM=32, MAX_ITER=256 ≈ ~30ms — heavy enough to dominate routing, light
// enough that a sweep to 128 doesn't saturate into timeouts on a 4-core box.
Route::get('/bench/mandelbrot', function () {
    $repeat = (int) env('BENCH_MANDELBROT_REPEAT', 1);
    $dim = (int) env('BENCH_MANDELBROT_DIM', 32);
    $maxIter = (int) env('BENCH_MANDELBROT_MAX_ITER', 256);
    $checksum = 0;

    for ($r = 0; $r < $repeat; $r++) {
        for ($y = -$dim; $y < $dim; $y++) {
            for ($x = -$dim; $x < $dim; $x++) {
                $zr = 0.0;
                $zi = 0.0;
                $cr = $x / $dim;   // grid scaled by DIM so the fractal region is stable
                $ci = $y / $dim;
                $i = 0;

                while ($zr * $zr + $zi * $zi < 4 && $i < $maxIter) {
                    $tmp = $zr * $zr - $zi * $zi + $cr;
                    $zi = 2 * $zr * $zi + $ci;
                    $zr = $tmp;
                    $i++;
                }

                $checksum += $i;
            }
        }
    }

    return response()->json([
        'repeat' => $repeat, 'dim' => $dim, 'max_iter' => $maxIter, 'checksum' => $checksum,
    ]);
});

// db — one indexed primary-key SELECT against MySQL 8 (realistic "app does a
// query" path). Scoped as each server's DEFAULT Octane DB behavior, not an
// isolated raw-query measurement (connection handling differs per server).
Route::get('/bench/db', function () {
    $id = random_int(1, 1000);
    $row = DB::table('bench_items')->where('id', $id)->first();

    return response()->json($row);
});
