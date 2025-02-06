from sqlmodel.ext.asyncio.session import AsyncSession
from sql_app import models
from schemas.media import CreatePdf, CreateVideo
from sqlmodel import select, delete
import datetime


class MediaRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_file(self, file_schema: CreatePdf):

        file = models.PdfFile(**file_schema.model_dump())
        self.db.add(file)
        await self.db.commit()
        await self.db.refresh(file)
        return file

    async def get_file_by_id(self, id: str):

        statement = select(models.PdfFile).filter_by(id=id).fetch(1)
        file = await self.db.exec(statement)
        return file.first()
    
    async def list_files_by_category(self, category: str):

        statment = select(models.PdfFile).filter_by(category=category)
        file = await self.db.exec(statment)
        return file.all()

    async def list_file(self, category_filter: str | None, filter_map: bool, sub_category_filter: str | None):

        statement = select(models.PdfFile)

        if filter_map:
            statement = statement.where(models.PdfFile.category != 'Mapa')

        if category_filter:
            statement = statement.where(
                models.PdfFile.category.ilike(f'%{category_filter}%')
            )

        if sub_category_filter:
            statement = statement.where(
                models.PdfFile.category.ilike(f'%{sub_category_filter}%')
            )

        files = await self.db.exec(statement)
        return files.all()

    async def update_file(self, file: models.PdfFile, file_update: dict):

        for key, value in file_update.items():
            if key in ('id', 'created_at', 'group'):
                continue

            if value is None:
                continue

            setattr(file, key, value)

        file.updated_at = datetime.datetime.now()
        await self.db.commit()
        await self.db.refresh(file)
        return file

    async def delete_file(self, file_id: str):

        statement = delete(models.PdfFile).where(models.PdfFile.id == file_id)
        await self.db.exec(statement)
        return await self.db.commit()

    async def create_video(self, video_schema: CreateVideo):

        video = models.Video(**video_schema.model_dump())
        self.db.add(video)
        await self.db.commit()
        await self.db.refresh(video)
        return video

    async def get_video_by_id(self, id: str):

        statement = select(models.Video).filter_by(id=id).fetch(1)
        video = await self.db.exec(statement)
        return video.first()

    async def list_video(self):

        statement = select(models.Video)
        videos = await self.db.exec(statement)
        return videos.all()
