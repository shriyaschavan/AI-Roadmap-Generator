# AI Roadmap Generator

## Overview

This is an AI-powered web application that generates customized AI implementation roadmaps for organizations. Users input their organization details (name, size, industry, AI maturity level, and strategic goals), and the application uses OpenAI's GPT-4o model to generate a structured 3-phase roadmap covering short-term (0-6 months), medium-term (6-12 months), and long-term (12-24 months) initiatives. The roadmap includes a visual Mermaid.js Gantt chart timeline and can be exported as a PDF.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Framework
- **Flask** serves as the web framework, handling routing, form processing, and template rendering
- Application entry point is `main.py` which imports the Flask app from `app.py`
- Routes are defined in `routes.py` and handle form submission, roadmap generation, PDF export, and history viewing

### Database Layer
- **PostgreSQL** database accessed via **Flask-SQLAlchemy** with a custom `DeclarativeBase`
- Single model `RoadmapGeneration` stores organization inputs and generated content
- Database URL configured via `DATABASE_URL` environment variable
- Connection pooling enabled with `pool_recycle=300` and `pool_pre_ping=True` for reliability

### AI Integration
- **OpenAI API** (GPT-4o model) generates roadmap content via `openai_service.py`
- System prompt instructs the model to produce structured phases with initiatives and a Mermaid Gantt chart
- API key configured via `OPENAI_API_KEY` environment variable

### Frontend Architecture
- **Jinja2 templates** with a base template (`base.html`) providing consistent layout
- **Tailwind CSS** via CDN for styling, following Material Design-inspired guidelines
- **Mermaid.js** renders Gantt chart visualizations client-side
- Typography uses Inter (primary) and JetBrains Mono (code/technical) from Google Fonts

### PDF Generation
- **WeasyPrint** converts HTML templates to PDF documents
- Dedicated `pdf_template.html` provides print-optimized styling

### Security
- Session secret configured via `SESSION_SECRET` environment variable
- ProxyFix middleware applied for proper handling behind reverse proxies

## External Dependencies

### Required Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API authentication
- `SESSION_SECRET` - Flask session encryption key

### Python Packages
- Flask and Flask-SQLAlchemy for web framework and ORM
- OpenAI Python client for API integration
- WeasyPrint for PDF generation
- Markdown for converting roadmap text to HTML

### CDN Resources
- Tailwind CSS for styling
- Mermaid.js for Gantt chart rendering
- Google Fonts (Inter, JetBrains Mono)