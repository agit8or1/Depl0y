"""Documentation API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from app.api.auth import get_current_user
import logging
import os
import markdown
from weasyprint import HTML, CSS
from datetime import datetime
import tempfile

logger = logging.getLogger(__name__)

router = APIRouter()

# Documentation files directory
DOCS_DIR = "/opt/depl0y/docs"
DOCS_FILES = {
    "install": "INSTALL.md",
    "deployment": "DEPLOYMENT.md",
    "cloud-quickstart": "CLOUD_IMAGES_QUICKSTART.md",
    "cloud-guide": "CLOUD_IMAGES_GUIDE.md",
    "readme": "README.md",
    "proxmox-api-tokens": "PROXMOX_API_TOKENS.md",
    "cloud-index": "docs/CLOUD_IMAGES_INDEX.md"
}


@router.get("/")
def list_documentation(current_user=Depends(get_current_user)):
    """List all available documentation"""
    docs = []
    for key, filename in DOCS_FILES.items():
        filepath = os.path.join(DOCS_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            docs.append({
                "id": key,
                "filename": filename,
                "title": _get_title(key),
                "size": size,
                "available": True
            })
        else:
            docs.append({
                "id": key,
                "filename": filename,
                "title": _get_title(key),
                "available": False
            })

    return {"docs": docs}


@router.get("/{doc_id}")
def get_documentation(
    doc_id: str,
    format: str = "markdown",
    current_user=Depends(get_current_user)
):
    """Get a specific documentation file"""
    if doc_id not in DOCS_FILES:
        raise HTTPException(status_code=404, detail="Documentation not found")

    filename = DOCS_FILES[doc_id]
    filepath = os.path.join(DOCS_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=404,
            detail=f"Documentation file {filename} not found on server"
        )

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        if format == "json":
            return JSONResponse({
                "id": doc_id,
                "filename": filename,
                "title": _get_title(doc_id),
                "content": content,
                "format": "markdown"
            })
        else:
            # Return plain text markdown
            return PlainTextResponse(content, media_type="text/markdown")

    except Exception as e:
        logger.error(f"Failed to read documentation {doc_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read documentation: {str(e)}"
        )


def _get_title(doc_id: str) -> str:
    """Get human-readable title for documentation"""
    titles = {
        "install": "Installation Guide",
        "deployment": "Deployment Guide",
        "cloud-quickstart": "Cloud Images - Quick Start",
        "cloud-guide": "Cloud Images - Complete Guide",
        "readme": "Getting Started with Depl0y",
        "proxmox-api-tokens": "Proxmox API Tokens Setup",
        "cloud-index": "Cloud Images Documentation Index"
    }
    return titles.get(doc_id, doc_id.replace("-", " ").title())


@router.get("/download/pdf")
def download_documentation_pdf(current_user=Depends(get_current_user)):
    """Generate and download complete documentation as PDF"""
    try:
        # Order of documentation to include in PDF
        doc_order = [
            "readme",
            "install",
            "deployment",
            "cloud-quickstart",
            "cloud-guide",
            "proxmox-api-tokens"
        ]

        # Build HTML content
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Depl0y Documentation</title>
            <style>
                @page {
                    size: A4;
                    margin: 2cm;
                    @top-center {
                        content: "Depl0y Documentation";
                        font-size: 10pt;
                        color: #666;
                    }
                    @bottom-center {
                        content: counter(page);
                        font-size: 10pt;
                        color: #666;
                    }
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 100%;
                }
                h1 {
                    color: #2563eb;
                    border-bottom: 3px solid #2563eb;
                    padding-bottom: 0.5rem;
                    margin-top: 2rem;
                    page-break-before: always;
                }
                h1:first-of-type {
                    page-break-before: avoid;
                }
                h2 {
                    color: #1e40af;
                    border-bottom: 2px solid #dbeafe;
                    padding-bottom: 0.3rem;
                    margin-top: 1.5rem;
                }
                h3 {
                    color: #4338ca;
                    margin-top: 1rem;
                }
                code {
                    background: #f3f4f6;
                    padding: 0.2rem 0.4rem;
                    border-radius: 3px;
                    font-family: "Courier New", monospace;
                    font-size: 0.9em;
                }
                pre {
                    background: #1e293b;
                    color: #e2e8f0;
                    padding: 1rem;
                    border-radius: 5px;
                    overflow-x: auto;
                    page-break-inside: avoid;
                }
                pre code {
                    background: none;
                    color: #10b981;
                    padding: 0;
                }
                ul, ol {
                    margin-left: 1.5rem;
                }
                li {
                    margin-bottom: 0.5rem;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 1rem 0;
                    page-break-inside: avoid;
                }
                th, td {
                    border: 1px solid #e5e7eb;
                    padding: 0.5rem;
                    text-align: left;
                }
                th {
                    background: #f9fafb;
                    font-weight: 600;
                }
                blockquote {
                    border-left: 4px solid #2563eb;
                    padding-left: 1rem;
                    margin: 1rem 0;
                    color: #6b7280;
                    font-style: italic;
                }
                a {
                    color: #2563eb;
                    text-decoration: none;
                }
                .cover-page {
                    text-align: center;
                    padding: 5rem 2rem;
                    page-break-after: always;
                }
                .cover-title {
                    font-size: 3rem;
                    color: #2563eb;
                    margin-bottom: 1rem;
                }
                .cover-subtitle {
                    font-size: 1.5rem;
                    color: #6b7280;
                    margin-bottom: 3rem;
                }
                .cover-info {
                    font-size: 1rem;
                    color: #9ca3af;
                }
                .toc {
                    page-break-after: always;
                }
                .toc h1 {
                    page-break-before: avoid;
                }
                .toc ul {
                    list-style: none;
                    padding-left: 0;
                }
                .toc li {
                    margin-bottom: 0.5rem;
                }
                .doc-section {
                    page-break-before: always;
                }
                .doc-section:first-of-type {
                    page-break-before: avoid;
                }
            </style>
        </head>
        <body>
            <!-- Cover Page -->
            <div class="cover-page">
                <h1 class="cover-title">Depl0y</h1>
                <p class="cover-subtitle">Complete Documentation</p>
                <p class="cover-info">Automated VM Deployment Panel for Proxmox VE</p>
                <p class="cover-info">Generated: """ + datetime.now().strftime("%B %d, %Y") + """</p>
                <p class="cover-info">Version 1.1.3</p>
            </div>

            <!-- Table of Contents -->
            <div class="toc">
                <h1>Table of Contents</h1>
                <ul>
        """

        # Add TOC entries
        for doc_id in doc_order:
            title = _get_title(doc_id)
            html_content += f'                    <li>{title}</li>\n'

        html_content += """
                </ul>
            </div>
        """

        # Add each documentation section
        for doc_id in doc_order:
            if doc_id not in DOCS_FILES:
                continue

            filename = DOCS_FILES[doc_id]
            filepath = os.path.join(DOCS_DIR, filename)

            if not os.path.exists(filepath):
                logger.warning(f"Documentation file {filename} not found, skipping")
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    md_content = f.read()

                # Convert markdown to HTML
                html_section = markdown.markdown(
                    md_content,
                    extensions=['extra', 'codehilite', 'tables', 'toc']
                )

                html_content += f'<div class="doc-section">\n{html_section}\n</div>\n'

            except Exception as e:
                logger.error(f"Failed to process {doc_id}: {e}")
                continue

        html_content += """
        </body>
        </html>
        """

        # Generate PDF
        logger.info("Generating PDF from HTML...")

        # Create temporary file for PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_path = tmp_file.name

        # Generate PDF using WeasyPrint
        HTML(string=html_content).write_pdf(pdf_path)

        logger.info(f"PDF generated successfully at {pdf_path}")

        # Return PDF file
        filename = f"Depl0y_Documentation_{datetime.now().strftime('%Y%m%d')}.pdf"

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=filename,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )
