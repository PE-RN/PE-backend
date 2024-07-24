from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from schemas.feedback import FeedbackCreate
from sql_app import models


class FeedbackRepository:

    def __init__(self, db: AsyncSession):

        self.db = db

    async def create_feedback(self, feedback_schema: FeedbackCreate):

        feedback = models.PdfFile(**feedback_schema.model_dump())
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback
