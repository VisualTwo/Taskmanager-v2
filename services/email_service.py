# services/email_service.py
from __future__ import annotations
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails"""
    
    def __init__(self, 
                 smtp_server: str = "localhost",
                 smtp_port: int = 587,
                 smtp_username: Optional[str] = None,
                 smtp_password: Optional[str] = None,
                 smtp_use_tls: bool = True,
                 from_email: str = "noreply@taskmanager.local",
                 enabled: bool = False):
        """
        Initialize email service
        
        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            smtp_use_tls: Whether to use TLS
            from_email: From email address
            enabled: Whether email sending is enabled
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.from_email = from_email
        self.enabled = enabled
        
        if not self.enabled:
            logger.warning("Email service is disabled. Emails will be logged but not sent.")
    
    def send_email(self, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            html_body: Optional HTML email body
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info(f"Email would be sent to {to_email} with subject '{subject}': {text_body}")
            return True
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Add text part
            text_part = MIMEText(text_body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_confirmation_email(self, to_email: str, full_name: str, confirmation_token: str, base_url: str) -> bool:
        """
        Send email confirmation email
        
        Args:
            to_email: User's email address
            full_name: User's full name
            confirmation_token: Email confirmation token
            base_url: Base URL of the application
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        confirmation_url = f"{base_url}/confirm-email?token={confirmation_token}"
        
        subject = "TaskManager - E-Mail bestätigen"
        
        text_body = f"""Hallo {full_name},

vielen Dank für Ihre Registrierung bei TaskManager!

Bitte bestätigen Sie Ihre E-Mail-Adresse, indem Sie auf den folgenden Link klicken:

{confirmation_url}

Nach der E-Mail-Bestätigung muss Ihr Konto noch von einem Administrator aktiviert werden.

Wenn Sie diese E-Mail nicht angefordert haben, können Sie sie ignorieren.

Mit freundlichen Grüßen
Ihr TaskManager-Team
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>E-Mail bestätigen</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #007bff;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 0 0 5px 5px;
            border: 1px solid #ddd;
            border-top: none;
        }}
        .button {{
            display: inline-block;
            background-color: #28a745;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>TaskManager</h1>
        <h2>E-Mail bestätigen</h2>
    </div>
    <div class="content">
        <p>Hallo {full_name},</p>
        
        <p>vielen Dank für Ihre Registrierung bei TaskManager!</p>
        
        <p>Bitte bestätigen Sie Ihre E-Mail-Adresse, indem Sie auf den folgenden Button klicken:</p>
        
        <p style="text-align: center;">
            <a href="{confirmation_url}" class="button">E-Mail bestätigen</a>
        </p>
        
        <p>Oder kopieren Sie diesen Link in Ihren Browser:</p>
        <p><a href="{confirmation_url}">{confirmation_url}</a></p>
        
        <p><strong>Wichtiger Hinweis:</strong> Nach der E-Mail-Bestätigung muss Ihr Konto noch von einem Administrator aktiviert werden, bevor Sie sich anmelden können.</p>
        
        <p>Wenn Sie diese E-Mail nicht angefordert haben, können Sie sie ignorieren.</p>
    </div>
    <div class="footer">
        <p>Mit freundlichen Grüßen<br>Ihr TaskManager-Team</p>
    </div>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, text_body, html_body)
    
    def send_password_reset_email(self, to_email: str, full_name: str, reset_token: str, base_url: str) -> bool:
        """
        Send password reset email
        
        Args:
            to_email: User's email address
            full_name: User's full name
            reset_token: Password reset token
            base_url: Base URL of the application
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        reset_url = f"{base_url}/reset-password?token={reset_token}"
        
        subject = "TaskManager - Passwort zurücksetzen"
        
        text_body = f"""Hallo {full_name},

Sie haben eine Passwort-Zurücksetzung für Ihr TaskManager-Konto angefordert.

Klicken Sie auf den folgenden Link, um ein neues Passwort zu setzen:

{reset_url}

Dieser Link ist 24 Stunden lang gültig.

Wenn Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.

Mit freundlichen Grüßen
Ihr TaskManager-Team
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Passwort zurücksetzen</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #dc3545;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 0 0 5px 5px;
            border: 1px solid #ddd;
            border-top: none;
        }}
        .button {{
            display: inline-block;
            background-color: #dc3545;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>TaskManager</h1>
        <h2>Passwort zurücksetzen</h2>
    </div>
    <div class="content">
        <p>Hallo {full_name},</p>
        
        <p>Sie haben eine Passwort-Zurücksetzung für Ihr TaskManager-Konto angefordert.</p>
        
        <p>Klicken Sie auf den folgenden Button, um ein neues Passwort zu setzen:</p>
        
        <p style="text-align: center;">
            <a href="{reset_url}" class="button">Neues Passwort setzen</a>
        </p>
        
        <p>Oder kopieren Sie diesen Link in Ihren Browser:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        
        <p><strong>Wichtiger Hinweis:</strong> Dieser Link ist 24 Stunden lang gültig.</p>
        
        <p>Wenn Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.</p>
    </div>
    <div class="footer">
        <p>Mit freundlichen Grüßen<br>Ihr TaskManager-Team</p>
    </div>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, text_body, html_body)
