"""Cria o usuario "sistema" usado para atribuir uploads, aprovacoes, sessoes
de chat e feedback quando nao ha login (ver `app/core/system_user.py`).

Uso:
    python scripts/seed_system_user.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session  # noqa: E402

from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.core.system_user import SYSTEM_USER_EMAIL, SYSTEM_USER_ID, SYSTEM_USER_NAME  # noqa: E402
from app.database.models import User  # noqa: E402
from app.database.session import engine  # noqa: E402

configure_logging()
logger = get_logger(__name__)


def seed_system_user() -> None:
    with Session(engine) as session:
        existing = session.get(User, SYSTEM_USER_ID)
        if existing:
            logger.info("seed_system_user.already_exists")
            return

        # `hashed_password` nao e usado para autenticacao (nao ha login neste
        # sistema) — apenas preenche a coluna obrigatoria com um valor
        # aleatorio, nunca verificado em nenhum fluxo.
        user = User(
            id=SYSTEM_USER_ID,
            email=SYSTEM_USER_EMAIL,
            hashed_password=uuid.uuid4().hex,
            full_name=SYSTEM_USER_NAME,
        )
        session.add(user)
        session.commit()
        logger.info("seed_system_user.created")


if __name__ == "__main__":
    seed_system_user()
