"""Bug Report API routes"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime

from app.api.auth import get_current_user
from app.models import User

router = APIRouter()
logger = logging.getLogger(__name__)


class BugReport(BaseModel):
    subject: str
    description: str
    page_url: Optional[str] = None
    error_details: Optional[str] = None
    browser_info: Optional[str] = None


@router.post("/")
async def submit_bug_report(
    bug_report: BugReport,
    current_user: User = Depends(get_current_user),
):
    """Submit a bug report via email"""
    try:
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[Depl0y Bug Report] {bug_report.subject}"
        msg['From'] = "agit8or@agit8or.net"
        msg['To'] = "agit8or@agit8or.net"

        # Create email body
        text_body = f"""
Bug Report from Depl0y

Reported by: {current_user.username} ({current_user.email})
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
Page URL: {bug_report.page_url or 'N/A'}

Description:
{bug_report.description}

Error Details:
{bug_report.error_details or 'N/A'}

Browser Info:
{bug_report.browser_info or 'N/A'}
"""

        html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif;">
    <h2 style="color: #ef4444;">Bug Report from Depl0y</h2>
    <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
      <tr>
        <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Reported by:</td>
        <td style="padding: 8px; border: 1px solid #ddd;">{current_user.username} ({current_user.email})</td>
      </tr>
      <tr>
        <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Time:</td>
        <td style="padding: 8px; border: 1px solid #ddd;">{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
      </tr>
      <tr>
        <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9; font-weight: bold;">Page URL:</td>
        <td style="padding: 8px; border: 1px solid #ddd;">{bug_report.page_url or 'N/A'}</td>
      </tr>
    </table>
    
    <div style="margin-bottom: 20px;">
      <h3 style="color: #333;">Description:</h3>
      <p style="white-space: pre-wrap; padding: 10px; background-color: #f5f5f5; border-left: 4px solid #ef4444;">{bug_report.description}</p>
    </div>
    
    <div style="margin-bottom: 20px;">
      <h3 style="color: #333;">Error Details:</h3>
      <pre style="padding: 10px; background-color: #f5f5f5; border-left: 4px solid #f59e0b; overflow-x: auto;">{bug_report.error_details or 'N/A'}</pre>
    </div>
    
    <div style="margin-bottom: 20px;">
      <h3 style="color: #333;">Browser Info:</h3>
      <p style="padding: 10px; background-color: #f5f5f5; border-left: 4px solid #3b82f6;">{bug_report.browser_info or 'N/A'}</p>
    </div>
  </body>
</html>
"""

        # Attach both text and HTML versions
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)

        # Send email using local sendmail
        with smtplib.SMTP('localhost') as server:
            server.send_message(msg)

        logger.info(f"Bug report sent from {current_user.username}: {bug_report.subject}")
        return {"status": "success", "message": "Bug report submitted successfully"}

    except Exception as e:
        logger.error(f"Failed to send bug report: {e}")
        raise HTTPException(status_code=500, detail="Failed to send bug report. Please try again later.")
