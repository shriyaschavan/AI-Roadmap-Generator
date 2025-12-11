from flask import render_template, request, flash, redirect, url_for, make_response
import markdown
import re
from weasyprint import HTML
from io import BytesIO
from app import app, db
from models import RoadmapGeneration
from openai_service import generate_roadmap


def parse_roadmap_initiatives(roadmap_text):
    """
    Parse roadmap text to extract individual initiatives.
    Returns list of initiative dicts with title, description, and phase.
    """
    initiatives = []
    current_phase = "Short-term"
    
    lines = roadmap_text.split('\n')
    current_initiative = None
    
    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Detect phase headers
        if 'phase 1' in line_lower or 'short-term' in line_lower or '0-6' in line_lower:
            current_phase = "Short-term (0-6 months)"
        elif 'phase 2' in line_lower or 'medium-term' in line_lower or '6-12' in line_lower:
            current_phase = "Medium-term (6-12 months)"
        elif 'phase 3' in line_lower or 'long-term' in line_lower or '12-24' in line_lower:
            current_phase = "Long-term (12-24 months)"
        
        # Pattern: **Initiative Name:** format
        initiative_match = re.match(r'\*\*Initiative Name:\*\*\s*(.+)', line_stripped, re.IGNORECASE)
        if initiative_match:
            if current_initiative and current_initiative.get('title'):
                initiatives.append(current_initiative)
            current_initiative = {
                'title': initiative_match.group(1).strip(),
                'description': '',
                'phase': current_phase
            }
            continue
        
        # Pattern: **Description:** line
        desc_match = re.match(r'[-*•]?\s*\*\*Description:\*\*\s*(.+)', line_stripped, re.IGNORECASE)
        if desc_match and current_initiative:
            current_initiative['description'] = desc_match.group(1).strip()
            continue
        
        # Pattern: Numbered or bullet initiative (fallback)
        bullet_match = re.match(r'^[-•*]\s*\*\*([^:*]+)\*\*[:\s]*(.*)$', line_stripped)
        if bullet_match:
            if current_initiative and current_initiative.get('title'):
                initiatives.append(current_initiative)
            title = bullet_match.group(1).strip()
            desc = bullet_match.group(2).strip() if bullet_match.group(2) else ''
            if title.lower() not in ['initiative name', 'description', 'priority']:
                current_initiative = {
                    'title': title,
                    'description': desc,
                    'phase': current_phase
                }
                continue
    
    # Add the last initiative
    if current_initiative and current_initiative.get('title'):
        initiatives.append(current_initiative)
    
    return initiatives


def assign_kpis(initiative, industry=None, goals=None):
    """
    Assign KPIs to an initiative based on keywords in title/description.
    Returns dict with KPI metadata.
    """
    title = (initiative.get('title', '') or '').lower()
    desc = (initiative.get('description', '') or '').lower()
    text = f"{title} {desc}"
    
    # Default KPIs
    result = {
        'primary_kpis': ['Outcome Metric Specific to Use Case'],
        'secondary_kpis': ['Adoption Rate', 'Time-to-Value'],
        'baseline': 'Current State',
        'target': 'Target State',
        'value_driver': 'Efficiency & Value Realization',
        'measurement_frequency': 'Monthly',
        'data_sources': ['Core Operational Systems', 'Data Warehouse']
    }
    
    # Chatbot / Customer Support
    if any(kw in text for kw in ['chatbot', 'customer support', 'customer service', 'call center', 'contact center', 'support ticket']):
        result = {
            'primary_kpis': ['Call Deflection Rate (%)', 'Average Handling Time'],
            'secondary_kpis': ['CSAT Score', 'NPS', 'First Contact Resolution'],
            'baseline': '20% deflection rate',
            'target': '45% deflection rate',
            'value_driver': 'Cost Savings & Customer Experience',
            'measurement_frequency': 'Monthly',
            'data_sources': ['Contact Center Platform', 'CRM', 'Ticketing System']
        }
    
    # Demand Forecasting / Inventory
    elif any(kw in text for kw in ['demand forecast', 'inventory', 'stock', 'supply chain', 'warehouse']):
        result = {
            'primary_kpis': ['Forecast Accuracy (%)', 'Stock-Out Rate (%)'],
            'secondary_kpis': ['Inventory Holding Cost', 'Order Fulfillment Rate'],
            'baseline': '70% forecast accuracy',
            'target': '90% forecast accuracy',
            'value_driver': 'Efficiency & Cost Savings',
            'measurement_frequency': 'Monthly',
            'data_sources': ['ERP System', 'Sales History', 'Inventory Management']
        }
    
    # Personalization / Recommendation / Marketing
    elif any(kw in text for kw in ['personalization', 'recommendation', 'marketing', 'campaign', 'targeting', 'customer segment']):
        result = {
            'primary_kpis': ['Conversion Rate (%)', 'Average Order Value'],
            'secondary_kpis': ['Click-Through Rate', 'Customer Lifetime Value', 'Email Open Rate'],
            'baseline': '2.5% conversion rate',
            'target': '4.5% conversion rate',
            'value_driver': 'Revenue Growth',
            'measurement_frequency': 'Monthly',
            'data_sources': ['Web Analytics', 'CRM', 'Marketing Automation Platform']
        }
    
    # Governance / Compliance / Risk
    elif any(kw in text for kw in ['governance', 'compliance', 'risk', 'ethics', 'audit', 'policy', 'regulation']):
        result = {
            'primary_kpis': ['Number of AI Incidents', 'Policy Adoption Rate (%)'],
            'secondary_kpis': ['Audit Findings', 'Compliance Breach Count', 'Training Completion'],
            'baseline': '0 formal policies',
            'target': '100% policy coverage',
            'value_driver': 'Risk Reduction',
            'measurement_frequency': 'Quarterly',
            'data_sources': ['Risk Registers', 'Audit Logs', 'Policy Management Tools']
        }
    
    # Sentiment Analysis / Feedback
    elif any(kw in text for kw in ['sentiment', 'feedback', 'nlp', 'text analysis', 'voice of customer']):
        result = {
            'primary_kpis': ['Sentiment Score', 'Insight Generation Rate'],
            'secondary_kpis': ['Response Time to Issues', 'Theme Detection Accuracy'],
            'baseline': 'Manual review process',
            'target': '95% automated classification',
            'value_driver': 'Customer Experience',
            'measurement_frequency': 'Weekly',
            'data_sources': ['Survey Platform', 'Social Media', 'Review Sites', 'CRM']
        }
    
    # Automation / Process / RPA
    elif any(kw in text for kw in ['automation', 'automate', 'rpa', 'process optimization', 'workflow']):
        result = {
            'primary_kpis': ['Process Time Reduction (%)', 'Error Rate Reduction (%)'],
            'secondary_kpis': ['FTE Hours Saved', 'Process Throughput', 'Cost per Transaction'],
            'baseline': '8 hours manual process',
            'target': '1 hour automated process',
            'value_driver': 'Efficiency & Cost Savings',
            'measurement_frequency': 'Monthly',
            'data_sources': ['Process Mining Tools', 'ERP', 'Workflow Systems']
        }
    
    # Predictive Analytics / Forecasting
    elif any(kw in text for kw in ['predictive', 'forecast', 'prediction', 'machine learning', 'ml model']):
        result = {
            'primary_kpis': ['Prediction Accuracy (%)', 'Model Performance (AUC/F1)'],
            'secondary_kpis': ['False Positive Rate', 'Lead Time Improvement'],
            'baseline': 'Reactive decision-making',
            'target': '85% prediction accuracy',
            'value_driver': 'Data-Driven Decisions',
            'measurement_frequency': 'Monthly',
            'data_sources': ['Data Warehouse', 'BI Platform', 'Operational Systems']
        }
    
    # Training / Skills / Center of Excellence
    elif any(kw in text for kw in ['training', 'skill', 'capability', 'center of excellence', 'coe', 'upskill', 'education']):
        result = {
            'primary_kpis': ['Training Completion Rate (%)', 'Skill Assessment Score'],
            'secondary_kpis': ['Employee Satisfaction', 'Knowledge Transfer Rate'],
            'baseline': '10% AI-literate workforce',
            'target': '60% AI-literate workforce',
            'value_driver': 'Capability Building',
            'measurement_frequency': 'Quarterly',
            'data_sources': ['LMS', 'HR Systems', 'Assessment Platforms']
        }
    
    # Data Platform / Infrastructure
    elif any(kw in text for kw in ['data platform', 'data infrastructure', 'data lake', 'data warehouse', 'mlops', 'data governance']):
        result = {
            'primary_kpis': ['Data Quality Score (%)', 'Data Availability (%)'],
            'secondary_kpis': ['Query Performance', 'Data Pipeline Success Rate'],
            'baseline': 'Fragmented data sources',
            'target': 'Unified data platform',
            'value_driver': 'Foundation & Enablement',
            'measurement_frequency': 'Monthly',
            'data_sources': ['Data Catalog', 'Monitoring Tools', 'ETL Logs']
        }
    
    # Sales / Revenue
    elif any(kw in text for kw in ['sales', 'revenue', 'lead scoring', 'opportunity', 'pipeline']):
        result = {
            'primary_kpis': ['Sales Conversion Rate (%)', 'Revenue per Lead'],
            'secondary_kpis': ['Sales Cycle Length', 'Win Rate', 'Average Deal Size'],
            'baseline': '15% lead conversion',
            'target': '25% lead conversion',
            'value_driver': 'Revenue Growth',
            'measurement_frequency': 'Monthly',
            'data_sources': ['CRM', 'Sales Analytics', 'Marketing Automation']
        }
    
    # Customer Insights / Analytics
    elif any(kw in text for kw in ['customer insight', 'analytics', 'dashboard', 'reporting', 'visualization', 'bi ']):
        result = {
            'primary_kpis': ['Decision Speed Improvement', 'Report Usage Rate'],
            'secondary_kpis': ['Data Freshness', 'User Adoption', 'Self-Service Rate'],
            'baseline': 'Weekly manual reports',
            'target': 'Real-time dashboards',
            'value_driver': 'Data-Driven Decisions',
            'measurement_frequency': 'Monthly',
            'data_sources': ['BI Platform', 'Data Warehouse', 'User Analytics']
        }
    
    return result


def score_ai_initiative(title, description=""):
    """
    Score an AI initiative on Impact, ROI, Risk, Complexity with Dependencies and Recommendation.
    Returns dict with all scoring metrics.
    """
    text = f"{title} {description}".lower()
    
    # Default scores
    scores = {
        'impact': 3,
        'roi': 3,
        'risk': 2,
        'complexity': 3,
        'dependencies': [],
        'recommendation': 'Proceed with standard implementation'
    }
    
    # High Impact indicators
    if any(kw in text for kw in ['revenue', 'customer', 'sales', 'growth', 'profit', 'strategic', 'competitive']):
        scores['impact'] = 5
    elif any(kw in text for kw in ['efficiency', 'automation', 'cost', 'savings', 'productivity']):
        scores['impact'] = 4
    elif any(kw in text for kw in ['training', 'governance', 'policy', 'foundation']):
        scores['impact'] = 3
    
    # ROI scoring
    if any(kw in text for kw in ['automation', 'chatbot', 'self-service', 'reduce cost', 'savings']):
        scores['roi'] = 5
    elif any(kw in text for kw in ['personalization', 'recommendation', 'upsell', 'conversion']):
        scores['roi'] = 4
    elif any(kw in text for kw in ['analytics', 'insight', 'dashboard', 'reporting']):
        scores['roi'] = 3
    elif any(kw in text for kw in ['governance', 'ethics', 'compliance', 'training']):
        scores['roi'] = 2
    
    # Risk scoring (1=low risk, 5=high risk)
    if any(kw in text for kw in ['pilot', 'poc', 'proof of concept', 'small scale', 'assessment']):
        scores['risk'] = 1
    elif any(kw in text for kw in ['training', 'education', 'awareness', 'governance']):
        scores['risk'] = 2
    elif any(kw in text for kw in ['integration', 'automation', 'workflow']):
        scores['risk'] = 3
    elif any(kw in text for kw in ['customer-facing', 'production', 'real-time', 'critical']):
        scores['risk'] = 4
    elif any(kw in text for kw in ['enterprise-wide', 'transformation', 'comprehensive', 'autonomous']):
        scores['risk'] = 5
    
    # Complexity scoring (1=simple, 5=complex)
    if any(kw in text for kw in ['simple', 'basic', 'standard', 'off-the-shelf', 'ready-made']):
        scores['complexity'] = 1
    elif any(kw in text for kw in ['training', 'policy', 'documentation', 'assessment']):
        scores['complexity'] = 2
    elif any(kw in text for kw in ['integration', 'api', 'workflow', 'dashboard']):
        scores['complexity'] = 3
    elif any(kw in text for kw in ['machine learning', 'predictive', 'nlp', 'custom model']):
        scores['complexity'] = 4
    elif any(kw in text for kw in ['enterprise', 'multi-system', 'real-time', 'advanced ai', 'autonomous']):
        scores['complexity'] = 5
    
    # Dependencies based on keywords
    deps = []
    if any(kw in text for kw in ['data', 'analytics', 'insight']):
        deps.append('Data Infrastructure')
    if any(kw in text for kw in ['integration', 'api', 'connect']):
        deps.append('System Integration')
    if any(kw in text for kw in ['model', 'ml', 'machine learning', 'ai']):
        deps.append('ML/AI Platform')
    if any(kw in text for kw in ['training', 'skill', 'capability']):
        deps.append('Staff Training')
    if any(kw in text for kw in ['governance', 'policy', 'compliance']):
        deps.append('AI Governance Framework')
    if any(kw in text for kw in ['customer', 'crm', 'support']):
        deps.append('CRM System')
    scores['dependencies'] = deps if deps else ['Standard IT Support']
    
    # Generate recommendation based on scores
    if scores['impact'] >= 4 and scores['risk'] <= 2:
        scores['recommendation'] = 'High Priority - Quick Win'
    elif scores['impact'] >= 4 and scores['complexity'] >= 4:
        scores['recommendation'] = 'Strategic Initiative - Plan Carefully'
    elif scores['roi'] >= 4 and scores['risk'] <= 3:
        scores['recommendation'] = 'Strong ROI - Proceed with Confidence'
    elif scores['risk'] >= 4 or scores['complexity'] >= 4:
        scores['recommendation'] = 'Pilot First - Validate Before Scaling'
    elif scores['impact'] <= 2:
        scores['recommendation'] = 'Lower Priority - Consider Deferring'
    else:
        scores['recommendation'] = 'Proceed with Standard Implementation'
    
    # Generate priority recommendation (High Priority / Medium Priority / Long-Term / Optional)
    priority_score = (scores['impact'] * 0.4) + (scores['roi'] * 0.4) - (scores['complexity'] * 0.2)
    if priority_score >= 3.0:
        scores['priority'] = 'High Priority'
    elif priority_score >= 1.5:
        scores['priority'] = 'Medium Priority'
    else:
        scores['priority'] = 'Long-Term / Optional'
    
    return scores


def inject_scores_into_html(roadmap_html, roadmap_text):
    """
    Inject scoring tags into the roadmap HTML after each initiative.
    Uses BeautifulSoup for reliable DOM-based parsing.
    Handles all initiative formats including "Initiative Name:" and bullet points.
    """
    from bs4 import BeautifulSoup
    
    # Parse initiatives from text
    initiatives = parse_roadmap_initiatives(roadmap_text)
    
    if not initiatives:
        return roadmap_html
    
    soup = BeautifulSoup(roadmap_html, 'html.parser')
    injected_titles = set()
    
    # Process each initiative and find its location in the HTML
    for init in initiatives:
        title = init['title']
        if title in injected_titles:
            continue
            
        scores = score_ai_initiative(title, init.get('description', ''))
        deps_text = ', '.join(scores['dependencies']) if scores['dependencies'] else 'None'
        
        score_html = f'''
<div class="initiative-meta bg-gray-50 border border-gray-200 rounded-lg p-3 mt-2 text-sm text-gray-700">
    <div><strong>Risk:</strong> {scores['risk']}/5</div>
    <div><strong>Complexity:</strong> {scores['complexity']}/5</div>
    <div><strong>Dependencies:</strong> {deps_text}</div>
    <div><strong>Recommendation:</strong> {scores['recommendation']}</div>
</div>
'''
        
        # Strategy 1: Look for "Initiative Name:" pattern
        strong_tags = soup.find_all('strong')
        injected = False
        
        for strong in strong_tags:
            strong_text = strong.get_text()
            if 'Initiative Name:' in strong_text:
                parent = strong.parent
                if parent:
                    parent_text = parent.get_text()
                    if title.lower() in parent_text.lower():
                        parent.insert_after(BeautifulSoup(score_html, 'html.parser'))
                        injected_titles.add(title)
                        injected = True
                        break
        
        if injected:
            continue
        
        # Strategy 2: Look for bold title directly (e.g., **Title**)
        for strong in strong_tags:
            strong_text = strong.get_text().strip()
            # Match if title is contained in strong text or vice versa
            if (title.lower() in strong_text.lower() or 
                strong_text.lower() in title.lower() or
                title.lower()[:20] in strong_text.lower()):
                parent = strong.parent
                if parent and parent.name in ['p', 'li']:
                    parent.insert_after(BeautifulSoup(score_html, 'html.parser'))
                    injected_titles.add(title)
                    injected = True
                    break
        
        if injected:
            continue
        
        # Strategy 3: Look for heading tags containing the title
        headings = soup.find_all(['h3', 'h4', 'h5'])
        for heading in headings:
            heading_text = heading.get_text().strip()
            if title.lower()[:20] in heading_text.lower():
                heading.insert_after(BeautifulSoup(score_html, 'html.parser'))
                injected_titles.add(title)
                break
    
    return str(soup)


def calculate_maturity_score(ai_maturity, goals):
    """Calculate AI maturity score based on inputs."""
    maturity_base = {'Low': 1.5, 'Medium': 3.0, 'High': 4.5}
    score = maturity_base.get(ai_maturity, 2.5)
    goal_bonus = min(len(goals) * 0.1, 0.5)
    return round(min(score + goal_bonus, 5.0), 1)


def get_industry_benchmark(industry, score):
    """Get industry benchmark percentile."""
    benchmarks = {
        'Technology': 3.8, 'Finance': 3.5, 'Healthcare': 3.0, 'Retail': 3.2,
        'Manufacturing': 2.8, 'Education': 2.5, 'Government': 2.3, 'Other': 2.8
    }
    avg = benchmarks.get(industry, 2.8)
    diff = score - avg
    percentile = min(max(50 + diff * 15, 10), 95)
    return round(avg, 1), int(percentile)


def render_markdown(text):
    """Convert markdown text to HTML."""
    if not text:
        return ""
    # Clean up any embedded <br> tags from old data
    text = text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    return markdown.markdown(text, extensions=['tables', 'fenced_code'])


@app.route("/")
def index():
    """Display the input form for roadmap generation."""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """Process form submission and generate AI roadmap."""
    organization_name = request.form.get("organization_name", "").strip()
    organization_size = request.form.get("organization_size", "").strip()
    industry = request.form.get("industry", "").strip()
    ai_maturity = request.form.get("ai_maturity", "").strip()
    goals = request.form.getlist("goals")
    
    if not organization_name or not organization_size or not industry or not ai_maturity:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("index"))
    
    if not goals:
        flash("Please select at least one goal.", "error")
        return redirect(url_for("index"))
    
    result = generate_roadmap(organization_name, organization_size, industry, ai_maturity, goals)
    
    if not result["success"]:
        flash(f"Failed to generate roadmap: {result['error']}", "error")
        return redirect(url_for("index"))
    
    generation = RoadmapGeneration(
        organization_name=organization_name,
        organization_size=organization_size,
        industry=industry,
        ai_maturity=ai_maturity,
        goals=", ".join(goals),
        roadmap_content=result["roadmap"],
        mermaid_chart=result["mermaid_chart"]
    )
    db.session.add(generation)
    db.session.commit()
    
    return redirect(url_for("view_roadmap", roadmap_id=generation.id))


@app.route("/roadmap/<int:roadmap_id>")
def view_roadmap(roadmap_id):
    """View a specific generated roadmap."""
    roadmap = RoadmapGeneration.query.get_or_404(roadmap_id)
    goals_list = [g.strip() for g in roadmap.goals.split(",")]
    
    # Calculate AI Maturity Score
    maturity_score = calculate_maturity_score(roadmap.ai_maturity, goals_list)
    industry_average, percentile = get_industry_benchmark(roadmap.industry, maturity_score)
    
    # Parse initiatives from roadmap content
    initiatives = parse_roadmap_initiatives(roadmap.roadmap_content or "")
    
    # Assign KPIs and scores to each initiative
    for initiative in initiatives:
        initiative['kpis'] = assign_kpis(initiative, industry=roadmap.industry, goals=goals_list)
        scores = score_ai_initiative(initiative['title'], initiative.get('description', ''))
        initiative['impact'] = scores['impact']
        initiative['roi'] = scores['roi']
        initiative['complexity'] = scores['complexity']
        initiative['priority'] = scores['priority']
    
    # Render markdown and inject scoring tags
    roadmap_html = render_markdown(roadmap.roadmap_content)
    roadmap_html_with_scores = inject_scores_into_html(roadmap_html, roadmap.roadmap_content or "")
    
    return render_template(
        "results.html",
        roadmap_id=roadmap.id,
        organization_name=roadmap.organization_name or "N/A",
        organization_size=roadmap.organization_size,
        industry=roadmap.industry,
        ai_maturity=roadmap.ai_maturity,
        goals=goals_list,
        roadmap=roadmap_html_with_scores,
        mermaid_chart=roadmap.mermaid_chart,
        created_at=roadmap.created_at,
        maturity_score=maturity_score,
        industry_average=industry_average,
        percentile=percentile,
        initiatives=initiatives
    )


@app.route("/history")
def history():
    """View all previously generated roadmaps."""
    roadmaps = RoadmapGeneration.query.order_by(RoadmapGeneration.created_at.desc()).all()
    return render_template("history.html", roadmaps=roadmaps)


@app.route("/roadmap/<int:roadmap_id>/pdf")
def download_pdf(roadmap_id):
    """Download roadmap as PDF."""
    roadmap = RoadmapGeneration.query.get_or_404(roadmap_id)
    goals_list = [g.strip() for g in roadmap.goals.split(",")]
    
    html_content = render_template(
        "pdf_template.html",
        organization_name=roadmap.organization_name or "N/A",
        organization_size=roadmap.organization_size,
        industry=roadmap.industry,
        ai_maturity=roadmap.ai_maturity,
        goals=goals_list,
        roadmap=render_markdown(roadmap.roadmap_content),
        created_at=roadmap.created_at
    )
    
    pdf_buffer = BytesIO()
    HTML(string=html_content).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    
    org_name = (roadmap.organization_name or "roadmap").replace(" ", "_")
    filename = f"AI_Roadmap_{org_name}.pdf"
    
    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@app.route("/roadmap/<int:roadmap_id>/send-email", methods=["POST"])
def send_pdf_email(roadmap_id):
    """Send roadmap PDF via email."""
    import os
    
    roadmap = RoadmapGeneration.query.get_or_404(roadmap_id)
    recipient_email = request.form.get("email", "").strip()
    custom_message = request.form.get("message", "").strip()
    
    if not recipient_email:
        flash("Please provide a recipient email address.", "error")
        return redirect(url_for("view_roadmap", roadmap_id=roadmap_id))
    
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    
    if not sendgrid_api_key:
        flash("Email service is not configured. Please contact the administrator to set up SendGrid.", "error")
        return redirect(url_for("view_roadmap", roadmap_id=roadmap_id))
    
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        import base64
        
        goals_list = [g.strip() for g in roadmap.goals.split(",")]
        html_content = render_template(
            "pdf_template.html",
            organization_name=roadmap.organization_name or "N/A",
            organization_size=roadmap.organization_size,
            industry=roadmap.industry,
            ai_maturity=roadmap.ai_maturity,
            goals=goals_list,
            roadmap=render_markdown(roadmap.roadmap_content),
            created_at=roadmap.created_at
        )
        
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_data = pdf_buffer.getvalue()
        
        org_name = (roadmap.organization_name or "Roadmap").replace(" ", "_")
        filename = f"AI_Roadmap_{org_name}.pdf"
        
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2563eb;">AI Implementation Roadmap</h2>
            <p>Please find attached the AI Implementation Roadmap for <strong>{roadmap.organization_name or 'your organization'}</strong>.</p>
            {f'<p style="background: #f8fafc; padding: 12px; border-left: 4px solid #2563eb; margin: 16px 0;"><em>{custom_message}</em></p>' if custom_message else ''}
            <p>This roadmap includes:</p>
            <ul>
                <li>3-phase implementation timeline (0-24 months)</li>
                <li>Initiative scoring and prioritization</li>
                <li>KPI & value measurement framework</li>
                <li>Industry benchmarking</li>
            </ul>
            <p style="color: #6b7280; font-size: 14px; margin-top: 24px;">Generated by AI Roadmap Generator</p>
        </body>
        </html>
        """
        
        message = Mail(
            from_email="noreply@ai-roadmap.replit.app",
            to_emails=recipient_email,
            subject=f"AI Implementation Roadmap - {roadmap.organization_name or 'Your Organization'}",
            html_content=email_body
        )
        
        encoded_pdf = base64.b64encode(pdf_data).decode()
        attachment = Attachment(
            FileContent(encoded_pdf),
            FileName(filename),
            FileType("application/pdf"),
            Disposition("attachment")
        )
        message.attachment = attachment
        
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_api_key)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            flash(f"Roadmap PDF sent successfully to {recipient_email}!", "success")
        else:
            flash("Failed to send email. Please try again.", "error")
            
    except ImportError:
        flash("Email service dependencies not installed. Please contact the administrator.", "error")
    except Exception as e:
        import logging
        logging.error(f"Email send error: {str(e)}")
        flash("Failed to send email. Please check the email address and try again.", "error")
    
    return redirect(url_for("view_roadmap", roadmap_id=roadmap_id))
