"""Identidade unica usada para atribuir acoes quando nao ha login.

O sistema e de uso livre, sem autenticacao: qualquer pessoa pode consultar,
enviar documentos e usar a curadoria. Varias tabelas (sessao de chat,
feedback, documento enviado/aprovado, trilha de auditoria) ainda referenciam
um usuario por chave estrangeira — em vez de exigir cadastro/login, todas as
acoes sao atribuidas a este unico usuario "sistema", criado uma vez por
`scripts/seed_system_user.py`.
"""

from __future__ import annotations

SYSTEM_USER_ID = "system"
SYSTEM_USER_EMAIL = "sistema@local"
SYSTEM_USER_NAME = "Sistema"
