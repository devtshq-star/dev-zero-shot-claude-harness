from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from config.settings import get_settings
from db.models import DatasetRow
from db.session import get_session
from domain.dataset import DatasetResponse
from tools.csv_profiling import load_and_profile_csv
from tools.data_quality import compute_data_quality_flags

router = APIRouter()


@router.post("/datasets")
def upload_datasets(files: list[UploadFile], session: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise api_error("INVALID_FILE", f"'{file.filename}' is not a .csv file", 400)

        dataset_id = str(uuid4())
        storage_path = upload_dir / f"{dataset_id}.csv"
        contents = file.file.read()
        storage_path.write_bytes(contents)

        try:
            df, profile = load_and_profile_csv(str(storage_path))
        except Exception as exc:  # noqa: BLE001
            storage_path.unlink(missing_ok=True)
            raise api_error("PARSE_ERROR", f"Failed to parse '{file.filename}': {exc}", 400)

        dataset = DatasetRow(
            id=dataset_id,
            name=file.filename,
            original_filename=file.filename,
            storage_path=str(storage_path),
            row_count=profile["row_count"],
            column_count=profile["column_count"],
            profile={"columns": profile["columns"], "duplicate_row_count": profile["duplicate_row_count"]},
        )
        session.add(dataset)
        session.flush()
        results.append(_to_response(dataset))

    return ok([r.model_dump(mode="json") for r in results])


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session)) -> dict:
    datasets = session.query(DatasetRow).order_by(DatasetRow.uploaded_at.desc()).all()
    return ok([_to_response(d).model_dump(mode="json") for d in datasets])


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, session: Session = Depends(get_session)) -> dict:
    dataset = session.get(DatasetRow, dataset_id)
    if dataset is None:
        raise api_error("NOT_FOUND", f"Dataset {dataset_id} not found", 404)
    return ok(_to_response(dataset).model_dump(mode="json"))


def _to_response(dataset: DatasetRow) -> DatasetResponse:
    return DatasetResponse(
        id=dataset.id,
        name=dataset.name,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        profile=dataset.profile,
        data_quality_flags=compute_data_quality_flags(dataset.profile, dataset.row_count),
        uploaded_at=dataset.uploaded_at,
    )
