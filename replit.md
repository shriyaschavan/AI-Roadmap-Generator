# AI Roadmap Generator

## Overview

This is an AI-powered web application that generates customized 3-phase AI implementation roadmaps for organizations. Users input their organization details (name, size, industry, AI maturity level, and goals), and the application uses OpenAI's API to generate a structured roadmap with short-term (0-6 months), medium-term (6-12 months), and long-term (12-24 months) phases. The application also generates Mermaid.js Gantt charts for visual timeline representation and supports PDF export of roadmaps.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Framework
- **Framework**: Flask (Python)
- **Why Flask**: Lightweight, straightforward web framework suitable for a focused single-purpose application. Handles form submissions, routing, and template rendering efficiently.

### Database
- **ORM**: Flask-SQLAlchemy with SQLAlchemy
- **Pattern**: Declarative base model pattern
- **Schema**: Single `RoadmapGeneration` model storing organization details, generated roadmap content, and Mermaid chart data
- **Connection**: Uses `DATABASE_URL` environment variable with connection pooling (pool_recycle=300, pool_pre_ping=True)

### AI Integration
- **Service**: OpenAI API (gpt-4o model)
- **Pattern**: Dedicated service module (`openai_service.py`) with lazy client initialization
- **Prompt Design**: System prompt instructs the AI to generate structured 3-phase roadmaps with Mermaid Gantt charts

### Frontend
- **Templating**: Jinja2 templates
- **Styling**: Tailwind CSS via CDN with custom configuration
- **Typography**: Inter (primary) and JetBrains Mono (monospace) from Google Fonts
- **Design System**: Material Design-inspired, enterprise-focused UI (documented in `design_guidelines.md`)
- **Charts**: Mermaid.js for Gantt chart rendering

### PDF Generation
- **Library**: WeasyPrint
- **Approach**: Server-side HTML-to-PDF conversion using dedicated PDF template

### Template Structure
- `base.html`: Shared layout with Tailwind config, fonts, and Mermaid initialization
- `index.html`: Input form for roadmap generation
- `results.html`: Displays generated roadmap with organization profile
- `history.html`: Lists previously generated roadmaps
- `pdf_template.html`: Print-optimized template for PDF export

### Key Routes
- `/`: Home page with input form
- `/generate` (POST): Processes form and generates roadmap
- `/history`: View all saved roadmaps
- `/view/<id>`: View specific roadmap
- `/download/<id>`: Download roadmap as PDF
- `/roadmap/<id>/send-email` (POST): Send roadmap PDF via email (requires SendGrid)

## External Dependencies

### APIs
- **OpenAI API**: Requires `OPENAI_API_KEY` environment variable for roadmap generation

### Environment Variables
- `SESSION_SECRET`: Flask session secret key
- `DATABASE_URL`: Database connection string
- `OPENAI_API_KEY`: OpenAI API authentication
- `SENDGRID_API_KEY`: (Optional) SendGrid API key for email functionality - not configured yet

### CDN Resources
- Tailwind CSS (cdn.tailwindcss.com)
- Mermaid.js (cdn.jsdelivr.net)
- Google Fonts (Inter, JetBrains Mono)

### Python Packages
- Flask and Flask-SQLAlchemy for web framework and ORM
- OpenAI Python client for API integration
- WeasyPrint for PDF generation
- Markdown for content rendering
- Werkzeug ProxyFix for proxy header handling