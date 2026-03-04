import asyncio
import json
import os
from pathlib import Path
from typing import Annotated, Any, Dict

from pydantic import BaseModel, Field

import pdfplumber
import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

try:
    from .ai_processor import GeminiProcessor
except ImportError:
    from ai_processor import GeminiProcessor

try:
    from .database import (
        delete_analysis,
        get_analysis,
        get_or_create_user,
        get_user_analyses,
        init_db,
        save_analysis,
    )
except ImportError:
    from database import (
        delete_analysis,
        get_analysis,
        get_or_create_user,
        get_user_analyses,
        init_db,
        save_analysis,
    )

try:
    from .extractor import extract_all_pages, extract_with_anchors
except ImportError:
    from extractor import extract_all_pages, extract_with_anchors

try:
    from .models import (
        AnchorConfig,
        AnalyzeResponse,
        AnalyzeStages,
        AnalyzeMetadata,
        CorreçãoItem,
        ExtractionResult,
        FullExtractionResult,
        Stage1Confidence,
        Stage1Data,
        Stage1OM,
        Stage1Requisicao,
        Stage1Result,
        Stage2Result,
        Stage3Result,
        Stage4Result,
        Stage5Result,
        Stage6Result,
        VerificationResult,
    )
except ImportError:
    from models import (
        AnchorConfig,
        AnalyzeResponse,
        AnalyzeStages,
        AnalyzeMetadata,
        CorreçãoItem,
        ExtractionResult,
        FullExtractionResult,
        Stage1Confidence,
        Stage1Data,
        Stage1OM,
        Stage1Requisicao,
        Stage1Result,
        Stage2Result,
        Stage3Result,
        Stage4Result,
        Stage5Result,
        Stage6Result,
        VerificationResult,
    )

try:
    from .stages import (
        stage1_identification,
        stage2_analysis,
        stage3_nc,
        stage4_documentation,
        stage5_dispatches,
        stage6_decision,
        nd_crosscheck,
    )
except ImportError:
    from stages import (
        stage1_identification,
        stage2_analysis,
        stage3_nc,
        stage4_documentation,
        stage5_dispatches,
        stage6_decision,
        nd_crosscheck,
    )

app = FastAPI(title="Licitacao PDF Extractor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(request: Request) -> Dict[str, str]:
    """Extrai informações básicas do usuário a partir dos headers enviados pelo frontend."""
    return {
        "email": request.headers.get("X-User-Email", "anonymous"),
        "name": request.headers.get("X-User-Name", "Anônimo"),
        "user_id": request.headers.get("X-User-Id", "anonymous"),
    }


@app.on_event("startup")
async def on_startup() -> None:
    """Inicializa o banco de dados PostgreSQL."""
    await init_db()


@app.post("/api/extract", response_model=ExtractionResult)
async def extract_pdf(
    file: Annotated[UploadFile, File(..., description="Arquivo PDF de licitação")],
):
    """
    Endpoint para extração de texto e tabelas de PDFs de processos licitatórios.

    - Recebe um PDF via upload.
    - Processa o arquivo buscando páginas relevantes com base em pontos âncora.
    - Remove o arquivo temporário após o processamento.
    - Retorna JSON com os dados extraídos.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="O arquivo enviado deve ser um PDF (.pdf)."
        )

    # Cria diretório temporário local para armazenar uploads.
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_path = temp_dir / file.filename

    try:
        # Salva o upload em disco.
        with temp_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Configuração padrão de âncoras.
        anchor_config = AnchorConfig()

        # Executa extração usando os pontos âncora.
        anchor_results = extract_with_anchors(temp_path, anchor_config)

        # Computa estatísticas básicas de páginas.
        with pdfplumber.open(temp_path) as pdf:
            total_pages = len(pdf.pages)

        # Páginas relevantes são as que aparecem em qualquer lista de resultados.
        relevant_pages = {
            page_result.page_number
            for anchor_list in anchor_results.values()
            for page_result in anchor_list
        }

        ignored_pages = max(total_pages - len(relevant_pages), 0)

        extraction_result = ExtractionResult(
            processed_pages=total_pages,
            ignored_pages=ignored_pages,
            anchor_config=anchor_config,
            results=anchor_results,
        )

        return extraction_result

    except Exception as exc:  # noqa: BLE001
        # Em produção, idealmente registrar o erro em um logger estruturado.
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar o PDF: {exc}",
        ) from exc

    finally:
        # Remove o arquivo PDF temporário após o processamento.
        try:
            if temp_path.is_file():
                os.remove(temp_path)
        except OSError:
            # Se não conseguir remover, apenas segue; não é crítico para o cliente.
            pass


@app.post("/api/extract-full", response_model=FullExtractionResult)
async def extract_pdf_full(
    file: Annotated[UploadFile, File(..., description="Arquivo PDF de licitação")],
):
    """
    Pipeline completo: extração com pdfplumber + estruturação com IA (Gemini)
    + verificação em segunda passagem. Retorna JSON estruturado e scores de confiança.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="O arquivo enviado deve ser um PDF (.pdf)."
        )

    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    try:
        with temp_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)

        anchor_config = AnchorConfig()
        anchor_results = extract_with_anchors(temp_path, anchor_config)

        with pdfplumber.open(temp_path) as pdf:
            total_pages = len(pdf.pages)

        relevant_pages = {
            page_result.page_number
            for anchor_list in anchor_results.values()
            for page_result in anchor_list
        }
        ignored_pages = max(total_pages - len(relevant_pages), 0)

        # Inicializa o processador Gemini (pode falhar se GEMINI_API_KEY não estiver definida).
        try:
            processor = GeminiProcessor()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        # Texto bruto concatenado (para verificação posterior).
        all_text_parts: list[str] = []
        dados: dict = {}

        # Cabeçalho: estrutura com IA.
        cabecalho_pages = anchor_results.get("cabecalho", [])
        if cabecalho_pages:
            texto_cabecalho = "\n\n".join(p.text for p in cabecalho_pages)
            all_text_parts.append(texto_cabecalho)
            dados["cabecalho"] = await asyncio.to_thread(
                processor.structure_header, texto_cabecalho
            )

        # Itens: texto e tabelas.
        itens_pages = anchor_results.get("itens", [])
        if itens_pages:
            textos_itens = [p.text for p in itens_pages]
            all_text_parts.extend(textos_itens)
            # Usa primeira página com tabela ou texto.
            input_itens: str | list = textos_itens[0] if textos_itens else ""
            if itens_pages[0].tables:
                input_itens = itens_pages[0].tables[0]
            dados["itens"] = await asyncio.to_thread(
                processor.structure_items, input_itens
            )

        # Despacho: análise com IA.
        despacho_pages = anchor_results.get("despacho", [])
        if despacho_pages:
            texto_despacho = "\n\n".join(p.text for p in despacho_pages)
            all_text_parts.append(texto_despacho)
            dados["despacho"] = await asyncio.to_thread(
                processor.analyze_dispatch, texto_despacho
            )

        # Fornecedor: estrutura com IA.
        fornecedor_pages = anchor_results.get("fornecedor", [])
        if fornecedor_pages:
            texto_fornecedor = "\n\n".join(p.text for p in fornecedor_pages)
            all_text_parts.append(texto_fornecedor)
            dados["fornecedor"] = await asyncio.to_thread(
                processor.structure_fornecedor, texto_fornecedor
            )

        texto_original = "\n\n---\n\n".join(all_text_parts)
        json_extraido = json.dumps(dados, ensure_ascii=False, indent=2)

        # Segunda passagem: verificação.
        verification_raw = await asyncio.to_thread(
            processor.verify_extraction, texto_original, json_extraido
        )
        score = float(verification_raw.get("score_confianca", 0.0))
        correcoes_raw = verification_raw.get("correcoes") or []
        correcoes = []
        for c in correcoes_raw:
            if isinstance(c, dict) and "campo" in c and "sugestao" in c:
                correcoes.append(
                    CorreçãoItem(
                        campo=c.get("campo", ""),
                        valor_atual=c.get("valor_atual", ""),
                        sugestao=c.get("sugestao", ""),
                        motivo=c.get("motivo", ""),
                    )
                )
        verification = VerificationResult(
            score_confianca=min(1.0, max(0.0, score)),
            correcoes=correcoes,
        )

        return FullExtractionResult(
            processed_pages=total_pages,
            ignored_pages=ignored_pages,
            dados=dados,
            verification=verification,
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Erro no pipeline de extração: {exc}",
        ) from exc

    finally:
        try:
            if temp_path.is_file():
                os.remove(temp_path)
        except OSError:
            pass


@app.post("/api/analyze")
async def analyze_pdf(
    request: Request,
    file: Annotated[UploadFile, File(..., description="Arquivo PDF de requisição")],
) -> StreamingResponse:
    """
    Pipeline completo de análise com envio de progresso via Server-Sent Events (SSE).

    - Extrai texto de todas as páginas.
    - Executa estágios 1–6 sequencialmente.
    - Envia eventos de progresso ao frontend.
    - Envia o resultado completo no evento final (`phase = \"complete\"`).
    """

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="O arquivo enviado deve ser um PDF (.pdf)."
        )

    async def event_generator():
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / file.filename

        try:
            # 0–10%: Extração de texto do PDF
            yield f"data: {json.dumps({'phase': 'extraction', 'progress': 2, 'message': 'Carregando arquivo PDF...'})}\n\n"

            with temp_path.open("wb") as buffer:
                content = await file.read()
                buffer.write(content)

            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'phase': 'extraction', 'progress': 5, 'message': 'Lendo conteúdo do PDF...'})}\n\n"

            extracted = extract_all_pages(temp_path)
            pages = extracted.get("pages", {}) or {}
            metadata_raw = extracted.get("metadata", {}) or {}
            pdf_path = extracted.get("pdf_path") or str(temp_path)
            image_pages = list(metadata_raw.get("image_pages") or [])
            total_pages = int(metadata_raw.get("total_paginas") or 0)

            yield f"data: {json.dumps({'phase': 'extraction_done', 'progress': 10, 'message': f'{total_pages} página(s) com texto extraído'})}\n\n"

            # 10–20%: Detecção de páginas-imagem
            if await request.is_disconnected():
                return

            image_count = len(image_pages)
            yield f"data: {json.dumps({'phase': 'image_detection', 'progress': 15, 'message': 'Detectando páginas escaneadas (imagem)...'})}\n\n"
            yield f"data: {json.dumps({'phase': 'image_detection_done', 'progress': 20, 'message': f'{image_count} página(s) identificadas como imagem'})}\n\n"

            # 20–30%: Estágio 1 — Identificação
            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'phase': 'stage1', 'progress': 20, 'message': 'Estágio 1 — Identificação (NUP, Requisição, OM)...'})}\n\n"

            page_1_text = pages.get("pagina_1", "") or ""
            stage1_raw = await asyncio.to_thread(stage1_identification.run, page_1_text)

            stage1_data_raw = stage1_raw.get("data") or {}
            stage1_conf_raw = stage1_raw.get("confidence") or {}

            stage1_data = Stage1Data(
                nup=stage1_data_raw.get("nup"),
                requisicao=Stage1Requisicao(
                    numero=(stage1_data_raw.get("requisicao", {}) or {}).get("numero"),
                    ano=(stage1_data_raw.get("requisicao", {}) or {}).get("ano"),
                    texto_original=(
                        stage1_data_raw.get("requisicao", {}) or {}
                    ).get("texto_original"),
                )
                if stage1_data_raw.get("requisicao") is not None
                else None,
                om=Stage1OM(
                    nome=(stage1_data_raw.get("om") or {}).get("nome"),
                    sigla=(stage1_data_raw.get("om") or {}).get("sigla"),
                    validada=bool(
                        (stage1_data_raw.get("om") or {}).get("validada", False)
                    ),
                    confianca=int(
                        (stage1_data_raw.get("om") or {}).get("confianca", 0)
                    ),
                )
                if stage1_data_raw.get("om") is not None
                else None,
            )

            stage1_confidence = Stage1Confidence(
                nup=int(stage1_conf_raw.get("nup", 0)),
                requisicao=int(stage1_conf_raw.get("requisicao", 0)),
                om=int(stage1_conf_raw.get("om", 0)),
                geral=int(stage1_conf_raw.get("geral", 0)),
            )

            stage1_result = Stage1Result(
                status=str(stage1_raw.get("status", "error")),
                method=str(stage1_raw.get("method", "regex")),
                data=stage1_data,
                confidence=stage1_confidence,
            )

            yield f"data: {json.dumps({'phase': 'stage1_done', 'progress': 30, 'message': 'Estágio 1 concluído.'})}\n\n"

            # 30–45%: Estágio 2 — Análise da requisição
            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'phase': 'stage2', 'progress': 30, 'message': 'Estágio 2 — Análise da requisição...'})}\n\n"

            stage2_raw = await asyncio.to_thread(
                stage2_analysis.run,
                pages,
                str(temp_path),
            )
            stage2_result = Stage2Result(**stage2_raw)

            yield f"data: {json.dumps({'phase': 'stage2_done', 'progress': 45, 'message': 'Estágio 2 concluído.'})}\n\n"

            # Identifica páginas da peça da requisição para uso no estágio 3.
            try:
                req_pages = stage2_analysis.find_requisition_pages(pages)
            except Exception:  # noqa: BLE001
                req_pages = []
            req_pages_list = list(req_pages or [])

            # 45–60%: Estágio 3 — Nota de Crédito
            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'phase': 'stage3', 'progress': 45, 'message': 'Estágio 3 — Nota de Crédito (NC)...'})}\n\n"

            stage3_raw = await asyncio.to_thread(
                stage3_nc.run,
                pages,
                req_pages,
                pdf_path,
                image_pages,
                total_pages,
            )
            stage3_result = Stage3Result(**stage3_raw)

            # Cruzamento ND × Itens (estágio 3 complementar)
            if (
                stage3_result
                and stage3_result.ncs
                and stage2_result
                and stage2_result.data
                and stage2_result.data.itens
            ):
                try:
                    primary_nc = stage3_result.ncs[0]
                    if primary_nc.destinos:
                        nd_cross = await nd_crosscheck.cross_check_nd_items(
                            nc_destinos=primary_nc.destinos,
                            items=stage2_result.data.itens,
                            nd_req=None,
                        )
                        stage3_result.nd_crosscheck = nd_cross
                except Exception as exc:  # noqa: BLE001
                    # Em caso de falha no cruzamento, apenas registra log e segue fluxo principal.
                    print(f"[Stage3] Falha no cruzamento ND × Itens: {exc}")

            yield f"data: {json.dumps({'phase': 'stage3_done', 'progress': 60, 'message': 'Estágio 3 concluído.'})}\n\n"

            # Páginas já usadas pelos estágios 1–3 (para os estágios seguintes ignorarem).
            used_pages: dict = {
                "stage1": {1},
                "requisition": set(req_pages_list),
            }
            stage2_dump = stage2_result.model_dump() if stage2_result else {}

            # 60–75%: Estágio 4 — Documentação
            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'phase': 'stage4', 'progress': 60, 'message': 'Estágio 4 — Documentação (CADIN, TCU, SICAF)...'})}\n\n"

            stage4_raw = await asyncio.to_thread(
                stage4_documentation.run,
                pages,
                stage2_dump,
                used_pages,
                None,  # analysis_date: usa data atual
            )
            stage4_result = Stage4Result(**stage4_raw)

            yield f"data: {json.dumps({'phase': 'stage4_done', 'progress': 75, 'message': 'Estágio 4 concluído.'})}\n\n"

            # 75–90%: Estágio 5 — Despachos
            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'phase': 'stage5', 'progress': 75, 'message': 'Estágio 5 — Despachos...'})}\n\n"

            stage5_raw = await asyncio.to_thread(
                stage5_dispatches.run,
                pages,
                used_pages,
            )
            stage5_result = Stage5Result(**stage5_raw)

            yield f"data: {json.dumps({'phase': 'stage5_done', 'progress': 90, 'message': 'Estágio 5 concluído.'})}\n\n"

            # 90–100%: Estágio 6 — Decisão Final
            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'phase': 'stage6', 'progress': 90, 'message': 'Estágio 6 — Decisão Final...'})}\n\n"

            stage6_raw = await asyncio.to_thread(
                stage6_decision.run,
                {
                    "stage1": stage1_result,
                    "stage2": stage2_result,
                    "stage3": stage3_result,
                    "stage4": stage4_result,
                    "stage5": stage5_result,
                },
            )
            stage6_result = Stage6Result(**stage6_raw)

            metadata = AnalyzeMetadata(
                total_paginas=int(metadata_raw.get("total_paginas") or 0),
                paginas_com_texto=int(metadata_raw.get("paginas_com_texto") or 0),
                paginas_sem_texto=int(metadata_raw.get("paginas_sem_texto") or 0),
                paginas_escaneadas=list(metadata_raw.get("paginas_escaneadas") or []),
            )

            stages = AnalyzeStages(
                stage1=stage1_result,
                stage2=stage2_result,
                stage3=stage3_result,
                stage4=stage4_result,
                stage5=stage5_result,
                stage6=stage6_result,
            )

            analyze_response = AnalyzeResponse(
                extraction={str(k): str(v) for k, v in pages.items()},
                metadata=metadata,
                stages=stages,
            )

            payload = analyze_response.model_dump(mode="json")
            yield f"data: {json.dumps({'phase': 'complete', 'progress': 100, 'message': 'Análise concluída.', 'result': payload})}\n\n"

        except HTTPException as exc:
            # Erros conhecidos: envia evento de erro antes de encerrar.
            error_payload = {
                "phase": "error",
                "progress": 100,
                "message": str(exc.detail),
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
        except Exception as exc:  # noqa: BLE001
            error_payload = {
                "phase": "error",
                "progress": 100,
                "message": f"Erro ao analisar o PDF: {exc}",
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            try:
                if temp_path.is_file():
                    os.remove(temp_path)
            except OSError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# --- Persistência de análises (SQLite) ---


class SaveAnalysisRequest(BaseModel):
    """Payload para POST /api/analyses."""

    dados_completos: Dict[str, Any] = Field(..., description="Resultado completo dos 6 estágios.")
    tempo_analise: int = Field(default=0, ge=0, description="Tempo de análise em segundos.")
    data_analise: str | None = Field(default=None, description="Data/hora da análise em ISO (opcional).")


class SaveAnalysisResponse(BaseModel):
    """Resposta de POST /api/analyses."""

    id: str = Field(..., description="UUID da análise salva.")
    success: bool = Field(default=True)


@app.post("/api/analyses", response_model=SaveAnalysisResponse)
async def save_analysis_endpoint(
    request: Request,
    body: SaveAnalysisRequest,
) -> SaveAnalysisResponse:
    """
    Salva uma análise no histórico, vinculada ao usuário autenticado.
    Recebe o resultado completo dos estágios e o tempo de análise.
    """
    user = get_current_user(request)

    # Logs de depuração do payload recebido.
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    logger.info("[SAVE] Análise recebida do usuário %s", user.get("user_id"))
    if isinstance(raw, dict):
        logger.info("[SAVE] Payload keys: %s", list(raw.keys()))
        logger.info(
            "[SAVE] Campos raiz: nup=%s veredicto=%s",
            raw.get("dados_completos", {}).get("stages", {})
            .get("stage1", {})
            .get("data", {})
            .get("nup"),
            raw.get("dados_completos", {}).get("stages", {})
            .get("stage6", {})
            .get("status"),
        )

    await get_or_create_user(user["user_id"], user["email"], user["name"])
    analysis_id = await save_analysis(
        user_id=user["user_id"],
        dados_completos=body.dados_completos,
        tempo_analise_sec=body.tempo_analise,
        data_analise_iso=body.data_analise,
    )
    return SaveAnalysisResponse(id=analysis_id, success=True)


@app.get("/api/analyses")
async def list_analyses(request: Request) -> list[Dict[str, Any]]:
    """
    Lista todas as análises salvas do usuário autenticado (sem dados_completos),
    ordenadas por data_analise desc.
    """
    user = get_current_user(request)
    return await get_user_analyses(user["user_id"])


@app.get("/api/analyses/{analysis_id}")
async def get_analysis_endpoint(analysis_id: str, request: Request) -> Dict[str, Any]:
    """Retorna uma análise completa com dados_completos, se pertencer ao usuário."""
    user = get_current_user(request)
    result = await get_analysis(analysis_id, user["user_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")

    # Loga o tipo de dados_completos para depuração.
    dados = result.get("dados_completos")
    logger.info(
        "[LOAD] Análise %s carregada para usuário %s. dados_completos type=%s",
        analysis_id,
        user.get("user_id"),
        type(dados),
    )
    return result


@app.delete("/api/analyses/{analysis_id}")
async def remove_analysis(analysis_id: str, request: Request) -> Dict[str, Any]:
    """Remove uma análise do banco, se pertencer ao usuário."""
    user = get_current_user(request)
    deleted = await delete_analysis(analysis_id, user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    return {"success": True, "id": analysis_id}


if __name__ == "__main__":
    # Permite rodar diretamente com: python -m backend.main
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=True)

