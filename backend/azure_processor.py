"""
Processador Azure Document Intelligence para extração de tabelas em imagens.
Usado como fallback no estágio 2 quando o Gemini não extrai itens (páginas com imagens grandes).
"""

import os
import base64
from typing import Optional

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest


def extract_table_text_with_azure(base64_image: str) -> Optional[str]:
    endpoint = os.getenv("AZURE_DI_ENDPOINT")
    key = os.getenv("AZURE_DI_KEY")
    if not endpoint or not key:
        print("[Azure] Credenciais não configuradas no .env.")
        return None

    try:
        client = DocumentIntelligenceClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )
        image_bytes = base64.b64decode(base64_image)

        analyze_request = AnalyzeDocumentRequest(bytes_source=image_bytes)
        poller = client.begin_analyze_document("prebuilt-layout", analyze_request)
        result = poller.result()

        if not result.tables:
            print("[Azure] Nenhuma tabela encontrada na imagem.")
            return None

        tsv_lines = []
        for table in result.tables:
            row_count = table.row_count
            col_count = table.column_count
            grid = [["" for _ in range(col_count)] for _ in range(row_count)]
            for cell in table.cells:
                content = (cell.content or "").replace("\n", " ").strip()
                grid[cell.row_index][cell.column_index] = content

            for row in grid:
                tsv_lines.append("\t".join(row))
            tsv_lines.append("\n---\n")

        return "\n".join(tsv_lines)
    except Exception as e:
        print(f"[Azure] Erro na extração: {e}")
        return None
