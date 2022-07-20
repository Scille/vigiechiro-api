import unicodedata
import smtplib
from email.message import EmailMessage


class Mail:
    def __init__(self, app):
        self.app = app

    def send(self, recipient, subject, body, attachements=[]):
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.app.config["MAIL_DEFAULT_SENDER"]
        msg['To'] = recipient
        msg.set_content(body)
        for filename, mime, data in attachements:
            unicodedata.normalize('NFKD', filename)
            maintype, subtype = mime.split("/")
            msg.add_attachment(
                data,
                filename=filename,
                maintype=maintype,
                subtype=subtype
            )

        if self.app.config["MAIL_MODE"].lower() == "ssl":
            self._send_ssl(recipient, msg)
        else:
            assert self.app.config["MAIL_MODE"].lower() == "tls"
            self._send_tls(recipient, msg)

    def _send_ssl(self, recipient, msg):
        with smtplib.SMTP(host=self.app.config["MAIL_SERVER"], port=self.app.config["MAIL_PORT"]) as server:
            server.starttls()
            server.login(user=self.app.config["MAIL_USERNAME"], password=self.app.config["MAIL_PASSWORD"])
            server.send_message(
                from_addr=self.app.config["MAIL_DEFAULT_SENDER"],
                to_addrs=[recipient],
                msg=msg,
            )

    def _send_tls(self, recipient, msg):
        with smtplib.SMTP_SSL(host=self.app.config["MAIL_SERVER"], port=self.app.config["MAIL_PORT"]) as server:
            server.ehlo()
            server.login(user=self.app.config["MAIL_USERNAME"], password=self.app.config["MAIL_PASSWORD"])
            server.send_message(
                from_addr=self.app.config["MAIL_DEFAULT_SENDER"],
                to_addrs=[recipient],
                msg=msg,
            )
