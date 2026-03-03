import base64
import io
import re
from pathlib import Path
from typing import Any, Dict, List, Literal

import pdfplumber

from .models import AnchorConfig, AnchorPageResult

# Para page_to_base64 é necessário: pip install pdf2image
# No Windows, instalar também o Poppler (pdf2image depende dele para converter PDF em imagem):
#   1. Baixar de https://github.com/ossamamehmood/Poppler-Windows/releases
#   2. Extrair o ZIP e adicionar a pasta bin/ ao PATH do sistema
#   OU passar poppler_path=... em convert_from_path() apontando para a pasta bin/
from pdf2image import convert_from_path

POPPLER_PATH = r"C:\Users\User\anaconda3\envs\projeto_pdf\Library\bin"


PageType = Literal["nativa", "escaneada"]


def detect_image_pages(pdf_path: str | Path) -> List[int]:
    """
    Retorna lista de páginas que são essencialmente imagens (pouco ou nenhum texto extraível).
    Critério: se o texto extraído tem menos de 100 caracteres (excluindo rodapé padrão),
    a página é provavelmente uma imagem.
    """
    image_pages: List[int] = []
    pdf_path = Path(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # Remover rodapé padrão que aparece mesmo em páginas-imagem
            clean = re.sub(
                r"Este documento.*?Pág \d+ de \d+", "", text, flags=re.IGNORECASE
            ).strip()
            if len(clean) < 100:
                image_pages.append(i + 1)  # 1-indexed
                print(
                    f"[Extractor] Página {i+1}: IMAGEM detectada "
                    f"(apenas {len(clean)} chars de texto)"
                )
    return image_pages


def page_to_base64(pdf_path: str | Path, page_number: int) -> str:
    """
    Converte uma página do PDF em imagem base64 para enviar ao Gemini.
    page_number é 1-indexed.
    Requer pdf2image e, no Windows, Poppler no PATH (ver comentário no topo do arquivo).
    """
    pdf_path = Path(pdf_path)
    try:
        images = convert_from_path(
            str(pdf_path),
            first_page=page_number,
            last_page=page_number,
            dpi=200,
            poppler_path=POPPLER_PATH,
        )
        if images:
            buffer = io.BytesIO()
            images[0].save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[Extractor] Erro ao converter página {page_number} para imagem: {exc}")
    return ""


def detect_page_type(page: pdfplumber.page.Page) -> PageType:
    """
    Detecta se uma página de PDF é 'nativa' ou 'escaneada'.
    """
    text = page.extract_text() or ""
    text_length = len(text.strip())
    image_count = len(page.images or [])

    if text_length >= 80:
        return "nativa"

    if text_length > 0 and image_count == 0:
        return "nativa"

    return "escaneada"


def _extract_tables_from_page(page: pdfplumber.page.Page) -> List[List[List[str]]]:
    """
    Extrai tabelas de uma página usando pdfplumber e normaliza o conteúdo.
    """
    raw_tables = page.extract_tables() or []
    normalized_tables: List[List[List[str]]] = []

    for table in raw_tables:
        normalized_table: List[List[str]] = []
        for row in table:
            normalized_row: List[str] = []
            for cell in row:
                if isinstance(cell, str):
                    normalized_row.append(cell.strip())
                elif cell is None:
                    normalized_row.append("")
                else:
                    normalized_row.append(str(cell).strip())
            normalized_table.append(normalized_row)
        if normalized_table:
            normalized_tables.append(normalized_table)

    return normalized_tables


def extract_with_anchors(
    pdf_path: str | Path, anchors_config: AnchorConfig
) -> Dict[str, List[AnchorPageResult]]:
    """
    Percorre as páginas do PDF, detecta pontos âncora no texto e
    extrai apenas as páginas relevantes.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF não encontrado em: {pdf_path}")

    results: Dict[str, List[AnchorPageResult]] = {
        key: [] for key in anchors_config.anchors.keys()
    }

    normalized_anchors: Dict[str, List[str]] = {
        anchor_type: [pattern.lower() for pattern in patterns]
        for anchor_type, patterns in anchors_config.anchors.items()
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            _ = detect_page_type(page)

            text = page.extract_text() or ""
            if not text.strip():
                continue

            normalized_text = text.lower()

            for anchor_type, patterns in normalized_anchors.items():
                matched = any(pattern in normalized_text for pattern in patterns)
                if not matched:
                    continue

                tables = _extract_tables_from_page(page)

                page_result = AnchorPageResult(
                    page_number=page_index,
                    text=text,
                    tables=tables,
                )

                results.setdefault(anchor_type, []).append(page_result)

    return results


def extract_all_pages(pdf_path: str | Path) -> Dict[str, Any]:
    """
    Extrai texto de todas as páginas do PDF em uma única passada.

    Retorno:
        {
            "pages": {"pagina_1": "...", "pagina_2": "...", ...},
            "metadata": {
                "total_paginas": N,
                "paginas_com_texto": M,
                "paginas_sem_texto": N - M,
                "paginas_escaneadas": [2, 5, ...],
                "image_pages": [6, 7, ...]  # páginas que são essencialmente imagens
            },
            "pdf_path": str  # path temporário; não deletar até fim dos estágios
        }
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF não encontrado em: {pdf_path}")

    pages: Dict[str, str] = {}
    paginas_com_texto = 0
    paginas_escaneadas: List[int] = []

    with pdfplumber.open(pdf_path) as pdf:
        total_paginas = len(pdf.pages)
        for idx, page in enumerate(pdf.pages, start=1):
            page_type = detect_page_type(page)
            if page_type == "escaneada":
                paginas_escaneadas.append(idx)

            text = page.extract_text() or ""
            if text.strip():
                paginas_com_texto += 1

            pages[f"pagina_{idx}"] = text

    image_pages = detect_image_pages(pdf_path)

    metadata: Dict[str, Any] = {
        "total_paginas": total_paginas,
        "paginas_com_texto": paginas_com_texto,
        "paginas_sem_texto": max(total_paginas - paginas_com_texto, 0),
        "paginas_escaneadas": paginas_escaneadas,
        "image_pages": image_pages,
    }

    return {
        "pages": pages,
        "metadata": metadata,
        "pdf_path": str(pdf_path.resolve()),
    }


