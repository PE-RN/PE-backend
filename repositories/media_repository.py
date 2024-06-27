from sqlmodel.ext.asyncio.session import AsyncSession
from sql_app import models
from schemas.media import CreatePdf, CreateVideo
from sqlmodel import select


class MediaRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pdf(self, pdf_schema: CreatePdf):

        pdf = models.PdfFile(**pdf_schema.model_dump())
        self.db.add(pdf)
        await self.db.commit()
        await self.db.refresh(pdf)
        return pdf

    async def get_pdf_by_id(self, id: str):

        statment = select(models.PdfFile).filter_by(id=id).fetch(1)
        pdf = await self.db.exec(statment)
        return pdf.first()

    async def list_pdf(self):

        statment = select(models.PdfFile)
        pdfs = await self.db.exec(statment)
        return pdfs.all()

    async def create_video(self, video_schema: CreateVideo):

        video = models.Video(**video_schema.model_dump())
        self.db.add(video)
        await self.db.commit()
        await self.db.refresh(video)
        return video

    async def get_video_by_id(self, id: str):

        statment = select(models.Video).filter_by(id=id).fetch(1)
        video = await self.db.exec(statment)
        return video.first()

    async def list_video(self):

        statment = select(models.Video)
        videos = await self.db.exec(statment)
        return videos.all()
