# Workflow helpers. PHP + Composer run on the HOST (install them locally, or use
# setup-php in CI) — only `composer install` needs Composer. The app servers, MySQL
# and wrk run in Docker; artisan commands that need the DB run inside an app
# container (it has PHP 8.4 + the mounted vendor/). `make help` lists the targets.
SHELL := /bin/bash
DC    := docker compose

.DEFAULT_GOAL := help
.PHONY: help build deps key env setup migrate bench smoke report down clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

build: ## Build the wrk load-generator image
	$(DC) build wrk

# The project targets php ^8.3 and the app containers run 8.4. --ignore-platform-req=php
# is a safety net so an even-older host can still assemble vendor/ (it runs in the
# 8.4 containers regardless).
deps: ## Install PHP dependencies into vendor/ (composer install on the host)
	composer install --no-interaction --prefer-dist --optimize-autoloader --ignore-platform-req=php

key: ## Generate APP_KEY in .env
	php artisan key:generate

env: ## Create .env from .env.example if it is missing
	@test -f .env || cp .env.example .env

setup: env deps key ## One-shot local bootstrap: .env + dependencies + APP_KEY

migrate: ## Start mysql and run migrations + seed the bench table (in a container)
	$(DC) up -d mysql
	$(DC) run --rm --no-deps swoole php artisan migrate --force

bench: ## Run the benchmark matrix (override via SERVERS=, WORKLOADS=, ... env)
	./benchmark.sh

smoke: ## Quick end-to-end smoke run (a few minutes)
	SERVERS="swoole fpm" WORKLOADS="hello db" CONCURRENCIES=8 RUNS=1 DURATION=5 WARMUP=2 ./benchmark.sh

report: ## Build RESULTS.md + docs/ from results/
	python3 bench/aggregate.py

down: ## Stop and remove all containers + volumes
	$(DC) --profile tools down -v

clean: down ## down + delete the raw result cells
	rm -f results/*.json
