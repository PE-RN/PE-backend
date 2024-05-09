import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailService:

    def __init__(self, host: str, port: str, email: str, password: str):
        self.host = host
        self.port = port
        self.email = email
        self.password = password

    def send_account_confirmation_account(self, to_email: str, ocupation: str, link_url: str) -> None | bool:

        """
            If has error raise exeception to be handled on controller layer , but try catch is used to enforce quit connection SMTP
        """

        server = smtplib.SMTP(host=self.host, port=self.port)
        try:
            server.ehlo()
            server.starttls()
            server.login(self.email, self.password)

            link_url = link_url.replace("&", "&amp;")
            link_url = link_url.replace("?", "&quest;")
            body = f'<h3 style="color:#0dace3;"> {ocupation.capitalize()} para confirmar seu email na plataforma por favor click  no link'
            body += f' <a style="display: inline-block;" href="{link_url}">LINK</a> !! <h3>'

            email_msg = MIMEMultipart()
            email_msg['From'] = self.email
            email_msg['To'] = to_email
            email_msg['Subject'] = "Confirmação de email Plataforma Atlas"
            email_msg.attach(MIMEText(body, 'html'))

            server.sendmail(email_msg['From'], email_msg['To'], email_msg.as_string())

        except Exception as e:
            server.quit()
            raise e
