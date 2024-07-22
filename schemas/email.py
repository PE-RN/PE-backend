from pydantic import BaseModel
from email.mime.image import MIMEImage


class EmailMessage(BaseModel):
    subject: str
    to_email: str
    html_content: str
    images: list

    @classmethod
    def with_default_logo_images(cls, subject: str, to_email: str, html_content: str):

        with open('utils/htmls/assets/estado.jpeg', 'rb') as estado_file:
            state = MIMEImage(estado_file.read(), _subtype='jpeg')
            state.add_header('Content-ID', '<estado>')

        with open('utils/htmls/assets/isi-er.jpeg', 'rb') as isi_er_file:
            isi_er = MIMEImage(isi_er_file.read(), _subtype='jpeg')
            isi_er.add_header('Content-ID', '<isi>')

        with open('utils/htmls/assets/logo.png', 'rb') as logo_file:
            logo = MIMEImage(logo_file.read(), _subtype='png')
            logo.add_header('Content-ID', '<logo>')
            logo.add_header('Content-Type', 'image/png; name="logo.png"')
            logo.add_header('Content-Disposition', 'inline; filename="logo.png"')

        default_images = [state, isi_er, logo]
        return cls(subject=subject, to_email=to_email, html_content=html_content, images=default_images)
