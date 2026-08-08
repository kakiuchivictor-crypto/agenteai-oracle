# Atalhos de desenvolvimento. Assume que o ambiente virtual ja esta ATIVADO
# (funciona identico em Windows/Linux/macOS dessa forma — veja o README para
# os comandos de ativacao de cada sistema operacional).
#
# Uso: make install / make test / make run-api ...
# No Windows sem `make` instalado, rode os comandos internos diretamente
# (copie a linha apos o `:` de cada alvo abaixo).

.PHONY: install migrate seed run-api run-frontend test lint evaluate docker-up docker-down clean

install:
	pip install --upgrade pip
	pip install -r requirements.txt

migrate:
	python -m alembic upgrade head

seed:
	python scripts/seed_system_user.py

run-api:
	python -m uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	python -m streamlit run frontend/streamlit_app/app.py

test:
	python -m pytest -q

test-cov:
	python -m pytest --cov=app --cov-report=term-missing -q

lint:
	python -m ruff check app tests scripts frontend

evaluate:
	python scripts/evaluate_rag.py

evaluate-fake:
	python scripts/evaluate_rag.py --fake

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
