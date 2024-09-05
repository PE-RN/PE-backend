from repositories.media_repository import MediaRepository
from typing import Annotated
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends, HTTPException, status
from sql_app.database import get_db
from schemas.media import CreatePdf, CreateVideo


class MediaController:

    def __init__(self, repository: MediaRepository):
        self.repository = repository

    @staticmethod
    async def inject_controller(db: Annotated[AsyncSession, Depends(get_db)]):
        return MediaController(
            repository=MediaRepository(db=db)
        )

    async def create_pdf(self, pdf: CreatePdf):
        return await self.repository.create_pdf(pdf)

    async def get_pdf(self, id: str):
        pdf = await self.repository.get_pdf_by_id(id)
        if not pdf:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado!")

    async def list_pdf(self):
        return await self.repository.list_pdf()

    async def create_video(self, video: CreateVideo):
        return await self.repository.create_video(video)

    async def get_video(self, id: str):
        video = await self.repository.get_video_by_id(id)
        if not video:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado!")

    async def list_video(self):
        return await self.repository.list_video()
