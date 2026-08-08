"""Rotas de ferramentas utilitarias sobre arquivos, fora do fluxo de RAG.

Diferente de `/documents`, estas rotas nao persistem nada no banco nem no
indice vetorial — sao transformacoes stateless sobre um arquivo enviado
(entra bytes, sai bytes), pensadas para o icone de clipe do chat.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies.providers import get_settings_dep
from app.core.config import Settings
from app.core.security import validate_upload
from app.documents.spreadsheet_tools import (
    build_summary_chart,
    clean_spreadsheet,
    dataframe_to_xlsx_bytes,
)
from app.schemas.api.tools import OrganizeSpreadsheetResponse

router = APIRouter(prefix="/tools", tags=["tools"])

_ALLOWED_EXTENSIONS = [".xlsx", ".csv"]
_PREVIEW_ROWS = 20


@router.post("/organize-spreadsheet", response_model=OrganizeSpreadsheetResponse)
async def organize_spreadsheet(
    file: UploadFile = File(...),
    generate_chart: bool = Form(False),
    request_text: str | None = Form(None),
    settings: Settings = Depends(get_settings_dep),
) -> OrganizeSpreadsheetResponse:
    filename = file.filename or "planilha"
    content = await file.read()

    validate_upload(
        filename=filename,
        content=content,
        allowed_extensions=_ALLOWED_EXTENSIONS,
        max_size_mb=settings.max_upload_size_mb,
    )

    result = clean_spreadsheet(filename=filename, content=content, request_text=request_text)
    currency_columns = [result.currency_format_column] if result.currency_format_column else None
    xlsx_bytes = dataframe_to_xlsx_bytes(result.dataframe, currency_columns=currency_columns)
    # Gerar o grafico tem um custo (matplotlib) e nem sempre e o que a pessoa
    # quer ao pedir so para "organizar" — so gera quando explicitamente
    # pedido (ver deteccao de intencao no Chat).
    chart_bytes = build_summary_chart(result.dataframe) if generate_chart else None

    base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
    preview = result.dataframe.head(_PREVIEW_ROWS).fillna("").astype(str)

    return OrganizeSpreadsheetResponse(
        summary=result.summary,
        file_name=f"{base_name}_organizado.xlsx",
        file_base64=base64.b64encode(xlsx_bytes).decode("ascii"),
        chart_base64=base64.b64encode(chart_bytes).decode("ascii") if chart_bytes else None,
        columns=[str(c) for c in result.dataframe.columns],
        preview_rows=preview.values.tolist(),
        total_rows=result.final_rows,
    )
