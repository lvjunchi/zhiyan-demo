from __future__ import annotations

import sqlite3
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from typing import Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import (
    backup_services,
    project_clear,
    document_imports,
    requirement_batches,
    part_selection,
    workflow_summary,
    coordination_progress,
    consistency_services,
    coordination_services,
    design_services,
    overview_services,
    workspace_services,
    package_services,
    sample_services,
    services,
    source_files,
    engineering_versions,
    engineering_batches,
    testing_services,
)
from .db import connect, run_migrations
from .document_text import MAX_FILE_BYTES, extract_text
from .errors import DomainValidationError
from .errors import ApiError
from .schemas import (
    ArtifactConfirmationCreate,
    CloseIssueRequest,
    ConflictCloseRequest,
    ConfirmationCreate,
    CoordinationMetricRequest,
    CoordinationRecordCreate,
    CoordinationRiskAcceptanceCreate,
    CoordinationTopicCreate,
    DesignArtifactRequest,
    FmeaItemUpdate,
    FmeaScoreConfirmation,
    MaterialPackageApprovalCreate,
    MaterialPackageCreate,
    ParseRequest,
    ProjectCreate,
    RecommendRequest,
    ReopenIssueRequest,
    RequirementCreate,
    RequirementUpdate,
    SampleComparisonCreate,
    SampleDeliveryCreate,
    SimilarProjectsRequest,
    SourceDocumentCreate,
    TestCaseUpdate,
    TestRunCreate,
    VariantAnalysisRequest,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "zhiyan.db"


async def get_db(request: Request) -> AsyncIterator[sqlite3.Connection]:
    # One local user; serialize database operations with restore activation.
    async with request.app.state.data_lock:
        connection = await run_in_threadpool(connect, request.app.state.db_path)
        try:
            yield connection
        finally:
            await run_in_threadpool(connection.close)


def _validation_details(exc: RequestValidationError) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for error in exc.errors():
        raw_input = error.get("input")
        safe_input = (
            raw_input
            if isinstance(raw_input, (str, int, float, bool, type(None)))
            else None
        )
        details.append(
            {
                "type": error.get("type"),
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg"),
                "input": safe_input,
            }
        )
    return details


def create_app(db_path: str | Path | None = None) -> FastAPI:
    base_db_path = str(db_path) if db_path is not None else str(DEFAULT_DB_PATH)
    resolved_db_path = str(
        backup_services.active_database(Path(base_db_path).resolve())
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        connection = connect(resolved_db_path)
        try:
            app.state.schema_version = run_migrations(connection)
        finally:
            connection.close()
        yield

    app = FastAPI(
        title="智研引擎 Demo API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.db_path = resolved_db_path
    app.state.base_db_path = Path(base_db_path).resolve()
    app.state.data_lock = asyncio.Lock()

    @app.exception_handler(sqlite3.OperationalError)
    async def persistence_error_handler(
        request: Request, exc: sqlite3.OperationalError
    ):
        logging.getLogger(__name__).warning(
            "SQLite operation failed: %s",
            getattr(exc, "sqlite_errorname", type(exc).__name__),
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "PERSISTENCE_UNAVAILABLE",
                    "message": "本地存储暂不可用，数据未保存，请检查连接或稍后重试",
                    "details": {},
                }
            },
        )

    @app.get("/api/system/backup")
    def download_backup(connection: sqlite3.Connection = Depends(get_db)):
        return JSONResponse(
            backup_services.create_backup(connection),
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''zhiyan-backup.json"
            },
        )

    @app.post("/api/projects/{project_id}/clear-preview")
    def preview_project_clear(
        project_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        return project_clear.preview(connection, project_id)

    @app.post("/api/projects/{project_id}/clear")
    def clear_project(
        project_id: str,
        payload: project_clear.ClearRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        result = project_clear.clear(
            connection, app.state.base_db_path, project_id, payload
        )
        app.state.db_path = result.pop("path")
        return result

    @app.get("/api/system/clear-backups/{backup_id}")
    def download_clear_backup(
        backup_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        return JSONResponse(
            project_clear.read_backup(app.state.base_db_path, backup_id),
            headers={
                "Content-Disposition": "attachment; filename=zhiyan-before-clear.json"
            },
        )

    @app.get("/api/projects/{project_id}/document-imports")
    def list_document_imports(
        project_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        return document_imports.list_imports(connection, project_id)

    @app.post("/api/projects/{project_id}/document-imports/extract")
    async def extract_import(
        project_id: str,
        request: Request,
        filename: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > MAX_FILE_BYTES:
                # Keep at most one byte over the limit; extraction records the real failure.
                content.extend(chunk[: MAX_FILE_BYTES + 1 - len(content)])
                break
            content.extend(chunk)
        return await run_in_threadpool(
            document_imports.extract, connection, project_id, filename, bytes(content)
        )

    @app.post("/api/projects/{project_id}/document-imports/{attempt_id}/discard")
    def discard_document_import(
        project_id: str,
        attempt_id: str,
        payload: document_imports.DiscardRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return document_imports.discard(connection, project_id, attempt_id)

    @app.post("/api/system/restore-preview")
    def preview_restore(
        payload: backup_services.RestorePreview,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        _, counts, projects = backup_services.validate_snapshot(payload.backup)
        return {
            "counts": counts,
            "projects": projects,
            "snapshot_sha256": payload.backup.sha256,
            "expected_state_hash": backup_services.create_backup(connection)["sha256"],
        }

    @app.post("/api/system/restore")
    def restore_backup(
        payload: backup_services.RestoreRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        restored = backup_services.restore_database(
            connection, app.state.base_db_path, payload
        )
        app.state.db_path = str(restored)
        return {
            "status": "restored",
            "original_retained": True,
            "reload_required": True,
        }

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求参数不合法",
                    "details": _validation_details(exc),
                }
            },
        )

    @app.get("/api/health")
    def health():
        try:
            connection = connect(app.state.db_path)
            try:
                return services.health(connection)
            finally:
                connection.close()
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "database": "disconnected"},
            )

    @app.get("/api/projects")
    def list_projects(
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.list_projects(connection)

    @app.post("/api/document-text")
    async def document_text(request: Request, filename: str):
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > MAX_FILE_BYTES:
                raise DomainValidationError("文档大小不得超过 8 MiB")
            content.extend(chunk)
        return extract_text(filename, bytes(content))

    @app.post("/api/projects", status_code=201)
    def create_project(
        payload: ProjectCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.create_project(connection, payload)

    @app.get("/api/projects/{project_id}")
    def get_project(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.get_project(connection, project_id)

    @app.get("/api/projects/{project_id}/workspace")
    def get_project_workspace(
        project_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        return workspace_services.get_workspace(connection, project_id)

    @app.get("/api/projects/{project_id}/overview")
    def get_project_overview(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return overview_services.get_project_overview(connection, project_id)

    @app.post("/api/projects/{project_id}/source-documents", status_code=201)
    def create_source_document(
        project_id: str,
        payload: SourceDocumentCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.create_source_document(connection, project_id, payload)

    @app.get("/api/projects/{project_id}/source-documents")
    def list_sources(project_id: str, connection: sqlite3.Connection = Depends(get_db)):
        return source_files.list_sources(connection, project_id)

    @app.get("/api/source-documents/{source_id}/original")
    def download_source_original(
        source_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        content, filename, media_type = source_files.download(connection, source_id)
        return Response(
            content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/api/coordination-topics/{topic_id}/progress")
    def get_progress(topic_id: str, connection: sqlite3.Connection = Depends(get_db)):
        return coordination_progress.detail(connection, topic_id)

    @app.post("/api/coordination-topics/{topic_id}/progress", status_code=201)
    def save_progress(
        topic_id: str,
        payload: coordination_progress.ProgressRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_progress.save(connection, topic_id, payload)

    @app.get("/api/projects/{project_id}/workflow-summary")
    def workflow_progress(
        project_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        return workflow_summary.summary(connection, project_id)

    @app.get("/api/projects/{project_id}/part-candidates")
    def part_choices(project_id: str, connection: sqlite3.Connection = Depends(get_db)):
        return part_selection.list_choices(connection, project_id)

    @app.post("/api/engineering-records/part/{object_id}/selection")
    def select_part(
        object_id: str,
        payload: part_selection.SelectionRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return part_selection.select(connection, object_id, payload)

    @app.get("/api/projects/{project_id}/engineering-records")
    def engineering_records(
        project_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        return engineering_versions.list_records(connection, project_id)

    @app.get("/api/projects/{project_id}/design-context")
    def design_context(
        project_id: str, connection: sqlite3.Connection = Depends(get_db)
    ):
        return engineering_versions.design_context(connection, project_id)

    @app.post("/api/projects/{project_id}/engineering-confirmations", status_code=201)
    def engineering_batch_confirm(
        project_id: str,
        payload: engineering_batches.BatchRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return engineering_batches.confirm(connection, project_id, payload)

    @app.get("/api/engineering-records/{kind}/{object_id}")
    def engineering_detail(
        kind: Literal["variant", "part"],
        object_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return engineering_versions.detail(connection, kind, object_id)

    @app.post(
        "/api/engineering-records/{kind}/{object_id}/confirmations", status_code=201
    )
    def engineering_confirm(
        kind: Literal["variant", "part"],
        object_id: str,
        payload: ArtifactConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return engineering_versions.confirm(connection, kind, object_id, payload)

    @app.get("/api/projects/{project_id}/requirements")
    def list_requirements(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.list_requirements(connection, project_id)

    @app.post("/api/projects/{project_id}/requirements", status_code=201)
    def create_requirement(
        project_id: str,
        payload: RequirementCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.create_requirement(connection, project_id, payload)

    @app.get("/api/projects/{project_id}/audit-events")
    def list_audit_events(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.list_audit_events(connection, project_id)

    @app.get("/api/projects/{project_id}/issues")
    def list_issues(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.list_issues(connection, project_id)

    @app.post("/api/source-documents/{source_document_id}/parse")
    def parse_source_document(
        source_document_id: str,
        payload: ParseRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        try:
            result = services.parse_source_document(
                connection, source_document_id, payload.display_code_map
            )
            document_imports.mark_parse(connection, source_document_id)
            return result
        except ApiError as exc:
            document_imports.mark_parse(connection, source_document_id, exc.message)
            raise

    @app.post("/api/projects/{project_id}/recommend-bases")
    def recommend_project_bases(
        project_id: str,
        payload: RecommendRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.recommend_project_bases(connection, project_id, payload.top_n)

    @app.post("/api/projects/{project_id}/variant-analysis")
    def analyze_variants(
        project_id: str,
        payload: VariantAnalysisRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.run_variant_analysis(
            connection, project_id, payload.base_display_code
        )

    @app.get("/api/issues/{issue_id}")
    def get_issue(
        issue_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.get_issue(connection, issue_id)

    @app.post("/api/issues/{issue_id}/close")
    def close_issue(
        issue_id: str,
        payload: CloseIssueRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.close_issue(connection, issue_id, payload)

    @app.post("/api/issues/{issue_id}/reopen")
    def reopen_issue(
        issue_id: str,
        payload: ReopenIssueRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.reopen_issue(connection, issue_id, payload)

    @app.post("/api/projects/{project_id}/similar-projects")
    def find_similar_projects(
        project_id: str,
        payload: SimilarProjectsRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.find_project_similar_projects(
            connection, project_id, payload.top_n
        )

    @app.post("/api/projects/{project_id}/design-review")
    def generate_design_review(
        project_id: str,
        payload: DesignArtifactRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.generate_design_review(
            connection, project_id, payload.base_display_code
        )

    @app.get("/api/projects/{project_id}/design-review")
    def get_design_review(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.get_design_review(connection, project_id)

    @app.post("/api/design-reviews/{review_id}/confirmations", status_code=201)
    def confirm_design_review(
        review_id: str,
        payload: ArtifactConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.confirm_design_review(connection, review_id, payload)

    @app.post("/api/projects/{project_id}/dfmea")
    def generate_dfmea(
        project_id: str,
        payload: DesignArtifactRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.generate_dfmea(
            connection, project_id, payload.base_display_code
        )

    @app.get("/api/projects/{project_id}/dfmea")
    def get_dfmea(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.get_dfmea(connection, project_id)

    @app.patch("/api/fmea-items/{item_id}")
    def update_fmea_item(
        item_id: str,
        payload: FmeaItemUpdate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.update_fmea_item(connection, item_id, payload)

    @app.post("/api/fmea-items/{item_id}/confirm-scores")
    def confirm_fmea_item_scores(
        item_id: str,
        payload: FmeaScoreConfirmation,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.confirm_fmea_item_scores(connection, item_id, payload)

    @app.post("/api/fmea-documents/{fmea_id}/confirmations", status_code=201)
    def confirm_dfmea(
        fmea_id: str,
        payload: ArtifactConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return design_services.confirm_dfmea(connection, fmea_id, payload)

    @app.post("/api/projects/{project_id}/test-plan")
    def generate_test_plan(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return testing_services.generate_test_plan(connection, project_id)

    @app.get("/api/projects/{project_id}/test-plan")
    def get_test_plan(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return testing_services.get_test_plan(connection, project_id)

    @app.post("/api/test-plans/{plan_id}/confirmations", status_code=201)
    def confirm_test_plan(
        plan_id: str,
        payload: ArtifactConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return testing_services.confirm_test_plan(connection, plan_id, payload)

    @app.patch("/api/test-cases/{case_id}")
    def update_test_case(
        case_id: str,
        payload: TestCaseUpdate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return testing_services.update_test_case(connection, case_id, payload)

    @app.post("/api/test-cases/{case_id}/confirmations", status_code=201)
    def confirm_test_case(
        case_id: str,
        payload: ArtifactConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return testing_services.confirm_test_case(connection, case_id, payload)

    @app.post("/api/test-cases/{case_id}/runs")
    def record_test_run(
        case_id: str,
        payload: TestRunCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return testing_services.record_test_run(connection, case_id, payload)

    @app.get("/api/projects/{project_id}/traceability-matrix")
    def get_traceability_matrix(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return testing_services.get_traceability_matrix(connection, project_id)

    @app.post("/api/projects/{project_id}/sample-deliveries", status_code=201)
    def create_sample_delivery(
        project_id: str,
        payload: SampleDeliveryCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return sample_services.create_sample_delivery(connection, project_id, payload)

    @app.get("/api/projects/{project_id}/sample-deliveries")
    def list_sample_deliveries(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return sample_services.list_sample_deliveries(connection, project_id)

    @app.get("/api/sample-deliveries/{delivery_id}")
    def get_sample_delivery(
        delivery_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return sample_services.get_sample_delivery(connection, delivery_id)

    @app.put("/api/sample-deliveries/{delivery_id}/file")
    async def upload_sample_file(
        delivery_id: str,
        request: Request,
        file_name: str,
        actor: str = "演示用户（未认证）",
    ):
        body = await request.body()
        connection = connect(request.app.state.db_path)
        try:
            return sample_services.upload_sample_file(
                connection,
                delivery_id,
                file_name=file_name,
                content_type=request.headers.get(
                    "content-type", "application/octet-stream"
                ),
                content=body,
                actor=actor,
            )
        finally:
            connection.close()

    @app.get("/api/sample-deliveries/{delivery_id}/file")
    def download_sample_file(
        delivery_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        row = sample_services.get_sample_file(connection, delivery_id)
        return Response(
            content=bytes(row["content"]),
            media_type=row["content_type"],
            headers={
                "x-content-sha256": row["content_hash"],
                "content-disposition": (
                    "attachment; filename*=UTF-8''" + quote(row["file_name"])
                ),
            },
        )

    @app.post("/api/sample-deliveries/{delivery_id}/comparison")
    def create_sample_comparison(
        delivery_id: str,
        payload: SampleComparisonCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return sample_services.create_sample_comparison(
            connection, delivery_id, payload
        )

    @app.get("/api/sample-deliveries/{delivery_id}/comparison")
    def get_sample_comparison(
        delivery_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return sample_services.get_sample_comparison(connection, delivery_id)

    @app.post(
        "/api/sample-comparisons/{comparison_id}/confirmations",
        status_code=201,
    )
    def confirm_sample_comparison(
        comparison_id: str,
        payload: ArtifactConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return sample_services.confirm_sample_comparison(
            connection, comparison_id, payload
        )

    @app.post(
        "/api/projects/{project_id}/coordination-topics",
        status_code=201,
    )
    def create_coordination_topic(
        project_id: str,
        payload: CoordinationTopicCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.create_coordination_topic(
            connection, project_id, payload
        )

    @app.get("/api/projects/{project_id}/coordination-topics")
    def list_coordination_topics(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.list_coordination_topics(connection, project_id)

    @app.get("/api/coordination-topics/{topic_id}")
    def get_coordination_topic(
        topic_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.get_coordination_topic(connection, topic_id)

    @app.post(
        "/api/coordination-topics/{topic_id}/records",
        status_code=201,
    )
    def create_coordination_record(
        topic_id: str,
        payload: CoordinationRecordCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.create_coordination_record(
            connection, topic_id, payload
        )

    @app.post(
        "/api/coordination-topics/{topic_id}/metrics",
        status_code=201,
    )
    def calculate_coordination_metrics(
        topic_id: str,
        payload: CoordinationMetricRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.calculate_coordination_metrics(
            connection, topic_id, payload
        )

    @app.get("/api/coordination-topics/{topic_id}/metrics")
    def get_latest_coordination_metrics(
        topic_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.get_latest_coordination_metrics(
            connection, topic_id
        )

    @app.get("/api/projects/{project_id}/coordination-overview")
    def get_coordination_overview(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.get_coordination_overview(connection, project_id)

    @app.post(
        "/api/coordination-topics/{topic_id}/risk-acceptances",
        status_code=201,
    )
    def accept_coordination_risk(
        topic_id: str,
        payload: CoordinationRiskAcceptanceCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return coordination_services.accept_coordination_risk(
            connection, topic_id, payload
        )

    @app.post("/api/projects/{project_id}/consistency-checks")
    def run_consistency_check(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.run_consistency_check(connection, project_id)

    @app.get("/api/projects/{project_id}/consistency-checks")
    def list_consistency_checks(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.list_consistency_checks(connection, project_id)

    @app.get("/api/projects/{project_id}/consistency-checks/latest")
    def get_latest_consistency_check(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.get_latest_consistency_check(connection, project_id)

    @app.get("/api/consistency-checks/{check_id}")
    def get_consistency_check(
        check_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.get_consistency_check(connection, check_id)

    @app.post(
        "/api/consistency-checks/{check_id}/confirmations",
        status_code=201,
    )
    def confirm_consistency_check(
        check_id: str,
        payload: ArtifactConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.confirm_consistency_check(
            connection, check_id, payload
        )

    @app.get("/api/projects/{project_id}/conflicts")
    def list_conflicts(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.list_conflicts(connection, project_id)

    @app.get("/api/conflicts/{conflict_id}")
    def get_conflict(
        conflict_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.get_conflict(connection, conflict_id)

    @app.post("/api/conflicts/{conflict_id}/close")
    def close_conflict(
        conflict_id: str,
        payload: ConflictCloseRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return consistency_services.close_conflict(connection, conflict_id, payload)

    @app.get("/api/requirements/{requirement_id}")
    def get_requirement(
        requirement_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.get_requirement(connection, requirement_id)

    @app.patch("/api/requirements/{requirement_id}")
    def update_requirement(
        requirement_id: str,
        payload: RequirementUpdate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.update_requirement(connection, requirement_id, payload)

    @app.get("/api/requirements/{requirement_id}/revisions")
    def list_revisions(
        requirement_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.list_revisions(connection, requirement_id)

    @app.get("/api/requirements/{requirement_id}/confirmations")
    def list_confirmations(
        requirement_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.list_confirmations(connection, requirement_id)

    @app.post("/api/requirements/{requirement_id}/confirmations", status_code=201)
    def confirm_requirement(
        requirement_id: str,
        payload: ConfirmationCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return services.confirm_requirement(connection, requirement_id, payload)

    @app.post("/api/projects/{project_id}/requirements/batch-preview")
    def preview_requirement_batch(
        project_id: str,
        payload: requirement_batches.BatchPreviewRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return requirement_batches.preview(connection, project_id, payload.items)

    @app.post("/api/projects/{project_id}/requirements/batch-confirm")
    def confirm_requirement_batch(
        project_id: str,
        payload: requirement_batches.BatchConfirmRequest,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return requirement_batches.confirm(connection, project_id, payload)

    @app.post("/api/projects/{project_id}/material-packages", status_code=201)
    def create_material_package(
        project_id: str,
        payload: MaterialPackageCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return package_services.create_material_package(connection, project_id, payload)

    @app.get("/api/projects/{project_id}/material-packages")
    def list_material_packages(
        project_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return package_services.list_material_packages(connection, project_id)

    @app.get("/api/material-packages/{package_id}")
    def get_material_package(
        package_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return package_services.get_material_package(connection, package_id)

    @app.get("/api/material-packages/{package_id}/download")
    def download_material_package(
        package_id: str,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        row = package_services.get_material_package_archive(connection, package_id)
        return Response(
            content=bytes(row["zip_content"]),
            media_type="application/zip",
            headers={
                "x-content-sha256": row["zip_hash"],
                "content-disposition": (
                    "attachment; filename*=UTF-8''"
                    + quote(f"{row['display_code']}.zip")
                ),
            },
        )

    @app.post(
        "/api/material-packages/{package_id}/approvals",
        status_code=201,
    )
    def approve_material_package(
        package_id: str,
        payload: MaterialPackageApprovalCreate,
        connection: sqlite3.Connection = Depends(get_db),
    ):
        return package_services.approve_material_package(
            connection, package_id, payload
        )

    return app


app = create_app()
