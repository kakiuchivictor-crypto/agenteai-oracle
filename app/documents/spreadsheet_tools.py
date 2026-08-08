"""Organizacao automatica e segura de planilhas (.xlsx/.csv) para o fluxo de
"organizar planilha" do chat.

Operacoes fixas e deterministicas, SEM execucao de codigo gerado por LLM:
remove linhas/colunas totalmente vazias, remove linhas duplicadas, remove
espacos em branco nas bordas de texto e nos nomes de coluna, preenche nomes
de coluna vazios/duplicados de forma previsivel, ordena por uma coluna
quando pedido explicitamente ("ordem crescente", "ordenar por X" — ver
`_detect_sort_intent`) e formata uma coluna numerica como moeda (R$) quando
pedido ("formate em reais" — ver `_wants_currency_format`). Tudo por
casamento de palavras-chave/nome de coluna contra o texto do pedido, nunca
codigo gerado ou interpretado pelo modelo de linguagem.

Quando o pedido menciona algo que a ferramenta nao consegue fazer com
seguranca (ex: formatar como moeda uma coluna que nao e numerica, ou pedir
ordenacao sem conseguir reconhecer nenhuma coluna), isso vira um aviso
explicito em `SpreadsheetCleaningResult.warnings` — nunca falha em silencio.
"""

from __future__ import annotations

import io
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

from app.core.exceptions import CorruptedFileError, InvalidFileError

SUPPORTED_EXTENSIONS = {"xlsx", "csv"}
_MAX_CHART_CATEGORIES = 15

_ASCENDING_KEYWORDS = ("crescente", "ascendente", "menor para maior", "do menor")
_DESCENDING_KEYWORDS = ("decrescente", "descendente", "maior para menor", "do maior")
_SORT_KEYWORDS = ("orden", "classific") + _ASCENDING_KEYWORDS + _DESCENDING_KEYWORDS
_CURRENCY_KEYWORDS = ("reais", "moeda", "r$", "brl")
_BRL_NUMBER_FORMAT = '"R$" #,##0.00'


@dataclass
class SpreadsheetCleaningResult:
    dataframe: pd.DataFrame
    original_rows: int
    original_columns: int
    empty_rows_removed: int
    empty_columns_removed: int
    duplicate_rows_removed: int
    sort_column: str | None = None
    sort_ascending: bool = True
    sort_column_guessed: bool = False
    currency_format_column: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def final_rows(self) -> int:
        return len(self.dataframe)

    @property
    def final_columns(self) -> int:
        return len(self.dataframe.columns)

    @property
    def summary(self) -> str:
        parts = []
        if self.empty_rows_removed:
            parts.append(f"{self.empty_rows_removed} linha(s) vazia(s) removida(s)")
        if self.empty_columns_removed:
            parts.append(f"{self.empty_columns_removed} coluna(s) vazia(s) removida(s)")
        if self.duplicate_rows_removed:
            parts.append(f"{self.duplicate_rows_removed} linha(s) duplicada(s) removida(s)")
        changes = ", ".join(parts) if parts else "nenhuma alteracao necessaria"
        summary = (
            f"Planilha organizada: {changes}. Resultado final: {self.final_rows} linha(s) x "
            f"{self.final_columns} coluna(s) (original: {self.original_rows} x "
            f"{self.original_columns})."
        )
        if self.sort_column:
            direction = "crescente" if self.sort_ascending else "decrescente"
            guess_note = (
                " (nenhuma coluna foi identificada no pedido, usei a primeira — peça de novo "
                "citando o nome da coluna se não era essa)"
                if self.sort_column_guessed
                else ""
            )
            summary += f" Ordenada pela coluna '{self.sort_column}' em ordem {direction}{guess_note}."
        if self.currency_format_column:
            summary += f" Coluna '{self.currency_format_column}' formatada como moeda (R$)."
        for warning in self.warnings:
            summary += f" ⚠️ {warning}"
        return summary


def _read_spreadsheet(filename: str, content: bytes) -> pd.DataFrame:
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise InvalidFileError(
            f"Formato '.{extension}' nao suportado para organizacao de planilhas. "
            f"Use .xlsx ou .csv."
        )

    buffer = io.BytesIO(content)
    try:
        if extension == "csv":
            return pd.read_csv(buffer)
        return pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - qualquer erro de parsing vira erro de dominio
        raise CorruptedFileError(f"Nao foi possivel ler a planilha '{filename}'.") from exc


def _is_blank(value: object) -> bool:
    if pd.isna(value):
        return True
    return isinstance(value, str) and value.strip() == ""


def _normalize_headers(columns: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: dict[str, int] = {}
    for index, raw in enumerate(columns, start=1):
        name = raw.strip() or f"Coluna {index}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        normalized.append(name)
    return normalized


def _normalize_for_match(text: str) -> str:
    """Remove acentos e caixa para casamento tolerante (ex: "salario" deve
    casar com a coluna 'Salário'). Sem isso, uma diferenca de acentuacao
    entre o nome da coluna e como a pessoa escreveu o pedido fazia o
    casamento falhar silenciosamente e cair no fallback errado."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _detect_sort_intent(request_text: str) -> bool | None:
    """Retorna True/False (ascendente/descendente) se o pedido mencionar
    ordenacao explicitamente, ou None se nao houver nenhuma palavra
    relacionada — nesse caso a planilha nao e ordenada (mesma logica
    conservadora usada para as demais operacoes desta ferramenta)."""
    lowered = request_text.lower()
    if not any(keyword in lowered for keyword in _SORT_KEYWORDS):
        return None
    wants_descending = any(keyword in lowered for keyword in _DESCENDING_KEYWORDS)
    return not wants_descending


def _wants_currency_format(request_text: str) -> bool:
    lowered = request_text.lower()
    return any(keyword in lowered for keyword in _CURRENCY_KEYWORDS)


def _find_mentioned_column(columns: list[str], request_text: str) -> str | None:
    """Casa o nome de alguma coluna real da planilha como substring do
    pedido (ex: "ordene por salario" casa a coluna 'Salário' mesmo com a
    diferenca de acento). Entre varias colunas que casarem, prefere o nome
    mais longo/especifico — evita que uma coluna curta e generica (ex:
    'Id') "roube" o casamento de uma mais especifica."""
    normalized_request = _normalize_for_match(request_text)
    matches = [
        column
        for column in columns
        if _normalize_for_match(column.strip())
        and _normalize_for_match(column.strip()) in normalized_request
    ]
    if not matches:
        return None
    return max(matches, key=lambda c: len(c.strip()))


def _numeric_sort_key(series: pd.Series) -> pd.Series:
    """Chave de ordenacao numerica para a coluna, mesmo quando os valores
    estao guardados como texto formatado (ex: "R$ 5.000,00"). Usada so para
    decidir a ORDEM das linhas — os valores originais da coluna nunca sao
    alterados. Sem isso, ordenar uma coluna de salario ja formatada como
    texto produzia ordem alfabetica ("R$ 1.200" antes de "R$ 900" porque
    "1" < "9" como caractere), nao numerica."""
    if pd.api.types.is_numeric_dtype(series):
        return series
    cleaned = series.astype(str).str.replace(r"[^\d,.\-]", "", regex=True)
    cleaned = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    # So usa a interpretacao numerica se a maioria dos valores realmente
    # parecer numero — senao mantem a ordenacao textual original (coluna
    # provavelmente nao e numerica de verdade).
    if numeric.notna().sum() >= max(1, int(len(series) * 0.5)):
        return numeric
    return series


def clean_spreadsheet(
    *, filename: str, content: bytes, request_text: str | None = None
) -> SpreadsheetCleaningResult:
    df = _read_spreadsheet(filename, content)
    original_rows, original_columns = df.shape

    df = df.map(lambda v: v.strip() if isinstance(v, str) else v)
    is_blank = df.map(_is_blank)

    empty_columns_mask = is_blank.all(axis=0)
    empty_columns_removed = int(empty_columns_mask.sum())
    df = df.loc[:, ~empty_columns_mask]
    is_blank = is_blank.loc[:, ~empty_columns_mask]

    empty_rows_mask = is_blank.all(axis=1)
    empty_rows_removed = int(empty_rows_mask.sum())
    df = df.loc[~empty_rows_mask]

    df.columns = _normalize_headers([str(c) for c in df.columns])

    before_dedupe = len(df)
    df = df.drop_duplicates(keep="first")
    duplicate_rows_removed = before_dedupe - len(df)

    df = df.reset_index(drop=True)

    sort_column: str | None = None
    sort_ascending = True
    sort_column_guessed = False
    currency_format_column: str | None = None
    warnings: list[str] = []

    if request_text:
        ascending = _detect_sort_intent(request_text)
        if ascending is not None and len(df.columns) > 0:
            sort_ascending = ascending
            matched = _find_mentioned_column(list(df.columns), request_text)
            sort_column = matched or df.columns[0]
            sort_column_guessed = matched is None
            sort_key = _numeric_sort_key(df[sort_column])
            df = (
                df.assign(_sort_key=sort_key)
                .sort_values(by="_sort_key", ascending=sort_ascending, kind="stable", na_position="last")
                .drop(columns="_sort_key")
                .reset_index(drop=True)
            )

        if _wants_currency_format(request_text):
            format_target = _find_mentioned_column(list(df.columns), request_text)
            if format_target is None:
                warnings.append(
                    "Não identifiquei qual coluna formatar como moeda — cite o nome da coluna "
                    'no pedido (ex.: "formate a coluna Salário em reais").'
                )
            elif not pd.api.types.is_numeric_dtype(df[format_target]):
                warnings.append(
                    f"Não formatei a coluna '{format_target}' como moeda porque os valores não "
                    "estão em formato numérico (evitei alterar os dados originais)."
                )
            else:
                currency_format_column = format_target

    return SpreadsheetCleaningResult(
        dataframe=df,
        original_rows=original_rows,
        original_columns=original_columns,
        empty_rows_removed=empty_rows_removed,
        empty_columns_removed=empty_columns_removed,
        duplicate_rows_removed=duplicate_rows_removed,
        sort_column=sort_column,
        sort_ascending=sort_ascending,
        sort_column_guessed=sort_column_guessed,
        currency_format_column=currency_format_column,
        warnings=warnings,
    )


def dataframe_to_xlsx_bytes(
    df: pd.DataFrame, *, sheet_name: str = "Organizado", currency_columns: list[str] | None = None
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        if currency_columns:
            worksheet = writer.sheets[sheet_name]
            for column_name in currency_columns:
                if column_name not in df.columns:
                    continue
                col_index = df.columns.get_loc(column_name) + 1  # openpyxl e 1-based
                for row_index in range(2, len(df) + 2):  # pula a linha de cabecalho
                    worksheet.cell(row=row_index, column=col_index).number_format = _BRL_NUMBER_FORMAT
    return buffer.getvalue()


def build_summary_chart(df: pd.DataFrame) -> bytes | None:
    """Grafico de barras heuristico: primeira coluna numerica como valor,
    primeira coluna categorica como rotulo (somando quando ha categorias
    repetidas). Sem coluna numerica, nao ha o que plotar — retorna None em
    vez de forcar um grafico sem sentido."""
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    if not numeric_columns or df.empty:
        return None

    value_column = numeric_columns[0]
    category_columns = [c for c in df.columns if c not in numeric_columns]

    if category_columns:
        label_column = category_columns[0]
        grouped = df.groupby(label_column, dropna=False)[value_column].sum()
        grouped = grouped.sort_values(ascending=False).head(_MAX_CHART_CATEGORIES)
        labels = [str(v) for v in grouped.index]
        values = grouped.to_numpy()
    else:
        limited = df.head(50)
        labels = [str(i + 1) for i in range(len(limited))]
        values = limited[value_column].to_numpy()

    if len(labels) == 0:
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(labels))))
    ax.barh(labels, values, color="#4C78A8")
    ax.set_xlabel(value_column)
    ax.invert_yaxis()
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=120)
    plt.close(fig)
    return buffer.getvalue()
