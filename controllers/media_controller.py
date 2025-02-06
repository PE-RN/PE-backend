from repositories.media_repository import MediaRepository
from typing import Annotated
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends, HTTPException, status, UploadFile
from pathlib import Path
from sql_app.database import get_db
from schemas.media import CreatePdf, CreateVideo
import shutil


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
            private_directory = Path("assets/public")
            private_directory.mkdir(parents=True, exist_ok=True)

            file_extension = Path(file.filename).suffix
            file_location = private_directory / f"{pdf.path}{file_extension}"

            try:
                with open(file_location, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving file: {str(e)}")

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
