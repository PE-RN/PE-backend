import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class EmailService:

    def __init__(self, host:str, port:str, email:str, password:str):
            self.host = host
            self.port = port
            self.email = email
            self.password = password

    async def send_account_confirmation_account(self, to_email:str, ocupation:str, link_url:str) -> None | bool:
        
        """
            If has error raise exeception to be handled on controller layer , but try catch is used to enforce quit connection SMTP
        """
        
        server = smtplib.SMTP(host=self.host,port=self.port)
        try:
            server.ehlo()
            server.starttls()
            server.login(self.email, self.password)

            body = f"<h2> {ocupation} para confirmar seu email na plataforma por favor click  no link {link_url}!! <h2>"

            email_msg = MIMEMultipart()
            email_msg['From'] = self.email
            email_msg['To'] = to_email
            email_msg['Subject'] = "Confirmação de email Plataforma Atlas"
            email_msg.attach(MIMEText(body,'html'))        

            server.sendmail(email_msg['From'], email_msg['To'], email_msg.as_string())

        except Exception as e:
            server.quit()
            raise e
        