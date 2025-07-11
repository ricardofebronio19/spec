# utils/email_sender.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# REMOVIDO: from config.settings import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS
# As configurações SMTP agora são passadas como argumentos para a função send_email.

def send_email(to_email, subject, body, smtp_server, smtp_port, smtp_username, smtp_password, smtp_use_tls):
    """
    Envia um e-mail usando as configurações SMTP fornecidas como argumentos.

    Args:
        to_email (str): O endereço de e-mail do destinatário.
        subject (str): O assunto do e-mail.
        body (str): O corpo do e-mail.
        smtp_server (str): O endereço do servidor SMTP (ex: "smtp.gmail.com").
        smtp_port (int): A porta do servidor SMTP (ex: 587).
        smtp_username (str): O nome de usuário do SMTP (o endereço de e-mail remetente).
        smtp_password (str): A senha ou senha de aplicativo do SMTP.
        smtp_use_tls (bool): Se deve usar TLS/SSL para a conexão.

    Returns:
        tuple: (bool, str) - True e mensagem de sucesso, ou False e mensagem de erro.
    """
    if not smtp_server or not smtp_username or not smtp_password:
        return False, "Configurações SMTP incompletas. E-mail não enviado."

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_use_tls:
                server.starttls() # Inicia o modo TLS (criptografia)
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_username, to_email, msg.as_string())
        return True, "E-mail enviado com sucesso!"
    except smtplib.SMTPAuthenticationError:
        return False, "Erro de autenticação SMTP. Verifique seu nome de usuário e senha (ou senha de aplicativo)."
    except smtplib.SMTPConnectError as e:
        return False, f"Erro de conexão SMTP: {e}. Verifique o servidor e a porta."
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {e}"

