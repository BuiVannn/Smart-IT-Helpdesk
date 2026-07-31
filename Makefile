.PHONY: help up down logs shell migrate revision seed test lint fmt reindex

help:            ## Hiện danh sách lệnh
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:              ## Khởi động toàn bộ hệ thống
	docker compose up -d --build && docker compose logs -f api

down:            ## Dừng hệ thống
	docker compose down

logs:            ## Xem log API
	docker compose logs -f api

shell:           ## Vào shell của container API
	docker compose exec api bash

migrate:         ## Chạy migration mới nhất
	docker compose exec api alembic upgrade head

revision:        ## Tạo migration mới — dùng: make revision m="mô tả"
	docker compose exec api alembic revision --autogenerate -m "$(m)"

seed:            ## Nạp dữ liệu khởi tạo
	docker compose exec api python scripts/seed.py

test:            ## Chạy toàn bộ test
	docker compose exec api pytest -v

test-unit:       ## Chỉ chạy unit test (nhanh, không cần DB)
	cd backend && pytest tests/unit -v

lint:            ## Kiểm tra code
	cd backend && ruff check . && black --check . && mypy app

fmt:             ## Tự động format code
	cd backend && ruff check --fix . && black .

reindex:         ## Dựng lại chỉ mục RAG
	docker compose exec api python scripts/reindex_kb.py --all
