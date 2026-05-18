from repositories.media_repository import MediaRepository
from typing import Annotated
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends, HTTPException, status, UploadFile
from pathlib import Path
from sql_app.database import get_db
from schemas.media import CreatePdf, CreateVideo
import shutil

# Allowlist: extension → expected MIME type
_ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".mp4":  "video/mp4",
    ".webm": "video/webm",
}

# 20 MB hard cap — reading _MAX_UPLOAD_BYTES+1 lets us detect over-sized
# uploads without buffering the entire file.
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class MediaController:

    def __init__(self, repository: MediaRepository):
        self.repository = repository

    @staticmethod
    async def inject_controller(db: Annotated[AsyncSession, Depends(get_db)]):
        return MediaController(
            repository=MediaRepository(db=db)
        )

    async def create_file(self, pdf: CreatePdf, file: UploadFile | None):
        if file:
            # --- Extension allowlist ---
            file_extension = Path(file.filename or "").suffix.lower()
            if file_extension not in _ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Tipo de ficheiro não permitido.",
                )

            # --- MIME type validation ---
            declared_mime = (file.content_type or "").split(";")[0].strip().lower()
            expected_mime = _ALLOWED_EXTENSIONS[file_extension]
            if declared_mime and declared_mime != expected_mime:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Tipo de conteúdo não corresponde à extensão.",
                )

            # --- File size limit (reads at most _MAX_UPLOAD_BYTES+1 bytes) ---
            content = await file.read(_MAX_UPLOAD_BYTES + 1)
            if len(content) > _MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Arquivo muito grande. Limite: 20 MB.",
                )

            # --- Path traversal prevention ---
            # Path().name strips any directory component; lstrip('.') removes
            # leading dots so names like '..' become empty strings.
            safe_stem = Path(pdf.path).name.lstrip(".")
            if not safe_stem:
                safe_stem = "upload"

            private_directory = Path("assets/public")
            private_directory.mkdir(parents=True, exist_ok=True)

            file_location = private_directory / f"{safe_stem}{file_extension}"

            try:
                file_location.write_bytes(content)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erro ao salvar arquivo.",
                )

            pdf.path = str(file_location)

        return await self.repository.create_file(pdf)

    async def get_file(self, id: str):
        pdf = await self.repository.get_file_by_id(id)
        if not pdf:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado!")
        return pdf

    async def list_file(self, category_filter: str | None, filter_map: bool, sub_category_filter: str | None):
        return await self.repository.list_file(category_filter, filter_map, sub_category_filter)

    async def update_file(self, file_update: dict, file_id: str):
        file = await self.repository.get_file_by_id(file_id)
        if not file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado!")

        return await self.repository.update_file(file, file_update)

    async def delete_file(self, file_id: str):
        file = await self.repository.get_file_by_id(file_id)
        if not file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado!")

        return await self.repository.delete_file(file_id)

    async def create_video(self, video: CreateVideo):
        return await self.repository.create_video(video)

    async def get_video(self, id: str):
        video = await self.repository.get_video_by_id(id)
        if not video:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado!")

    async def list_video(self):
        return await self.repository.list_video()
