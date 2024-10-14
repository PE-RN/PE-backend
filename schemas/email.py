from pydantic import BaseModel
from email.mime.image import MIMEImage


class EmailMessage(BaseModel):
    subject: str
    to_email: str
    html_content: str
    images: list

    @classmethod
    def with_default_logo_images(cls, subject: str, to_email: str, html_content: str):

        with open('utils/htmls/assets/GOVERNO_DO_ESTADO_SEDEC.png', 'rb') as estado_file:
            state = MIMEImage(estado_file.read(), _subtype='png')
            state.add_header('Content-ID', '<estado>')
            state.add_header('Content-Type', 'image/png; name="estado.png"')
            state.add_header('Content-Disposition', 'inline; filename="estado.png"')

        with open('utils/htmls/assets/ISI_ER.png', 'rb') as isi_er_file:
            isi_er = MIMEImage(isi_er_file.read(), _subtype='png')
            isi_er.add_header('Content-ID', '<isi>')
            isi_er.add_header('Content-Type', 'image/png; name="isi.png"')
            isi_er.add_header('Content-Disposition', 'inline; filename="isi.png"')

        with open('utils/htmls/assets/logo.png', 'rb') as logo_file:
            logo = MIMEImage(logo_file.read(), _subtype='png')
            logo.add_header('Content-ID', '<logo>')
            logo.add_header('Content-Type', 'image/png; name="logo.png"')
            logo.add_header('Content-Disposition', 'inline; filename="logo.png"')

        default_images = [state, isi_er, logo]
        return cls(subject=subject, to_email=to_email, html_content=html_content, images=default_images)
