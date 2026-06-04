<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Backing table for the /bench/db workload. Seeded here in up() so a single
 * `php artisan migrate --force` is all the harness needs to prepare the DB
 * workload — no separate seeder step.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('bench_items', function (Blueprint $table) {
            $table->id(); // indexed primary key — the /bench/db lookup key
            $table->string('sku', 32);
            $table->string('name');
            $table->unsignedInteger('price');
            $table->timestamp('created_at')->nullable();
        });

        // Seed 1000 rows in chunks so the indexed PK lookup has realistic data.
        $now = now();
        foreach (array_chunk(range(1, 1000), 100) as $chunk) {
            $rows = array_map(fn ($i) => [
                'sku' => sprintf('SKU-%05d', $i),
                'name' => "Benchmark Item {$i}",
                'price' => ($i * 37) % 10000,
                'created_at' => $now,
            ], $chunk);
            DB::table('bench_items')->insert($rows);
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('bench_items');
    }
};
