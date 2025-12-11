from flask import render_template, request, flash, redirect, url_for, make_response
import markdown
import re
from weasyprint import HTML
from io import BytesIO
from app import app, db
from models import RoadmapGeneration
from openai_service import generate_roadmap


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


def calculate_maturity_score(ai_maturity, goals_list):
    """
    Calculate AI Maturity Score based on current maturity level and selected goals.
    Returns tuple of (final_score, industry_average, percentile)
    """
    # Base scores by maturity level
    base_scores = {
        "Low": 1.5,
        "Medium": 3.0,
        "High": 4.5
    }
    
    # Goal-based weight adjustments
    goal_weights = {
        "Automation": 0.2,
        "Analytics": 0.2,
        "Customer Experience": 0.1,
        "Operational Efficiency": 0.1,
        "Innovation": 0.2,
        "Cost Reduction": 0.1,
        "Revenue Growth": 0.1,
        "Risk Management": 0.1,
        "Data-Driven Decisions": 0.2,
        "Employee Productivity": 0.1
    }
    
    # Get base score
    base_score = base_scores.get(ai_maturity, 2.5)
    
    # Calculate adjustment from selected goals
    adjustment = sum(goal_weights.get(goal, 0.0) for goal in goals_list)
    
    # Final score capped between 1.0 and 5.0
    final_score = round(min(max(base_score + adjustment, 1.0), 5.0), 2)
    
    return final_score


def get_industry_benchmark(industry, final_score):
    """
    Get industry benchmark and calculate percentile rank.
    Returns tuple of (industry_average, percentile)
    
    Percentile represents what percentage of companies in the industry
    the organization outperforms, based on comparing their score to the benchmark.
    """
    # Industry benchmark scores
    industry_benchmarks = {
        "Financial Services": 3.8,
        "Healthcare": 3.0,
        "Retail": 3.2,
        "Manufacturing": 2.9,
        "Public Sector": 2.4,
        "Technology": 4.2
    }
    
    # Get industry average (default 3.1)
    industry_average = industry_benchmarks.get(industry, 3.1)
    
    # Calculate percentile rank (0-100 scale)
    # Maps score relative to industry average onto a percentile distribution
    # Score at average = 50th percentile, above/below scales proportionally
    ratio = final_score / industry_average
    
    if ratio <= 0.5:
        percentile = 10.0
    elif ratio >= 1.5:
        percentile = 95.0
    elif ratio < 1.0:
        # Below average: map 0.5-1.0 ratio to 10-50 percentile
        percentile = 10 + (ratio - 0.5) * 80
    else:
        # Above average: map 1.0-1.5 ratio to 50-95 percentile
        percentile = 50 + (ratio - 1.0) * 90
    
    return industry_average, round(percentile, 1)


def score_ai_initiative(text, phase=""):
    """
    Score an AI initiative based on heuristic analysis of the text.
    Returns dict with impact, roi, risk, complexity scores (1-5), dependencies list, and recommendations.
    """
    text_lower = text.lower()
    
    # Impact score based on strategic alignment keywords
    impact_keywords = {
        5: ['transform', 'enterprise-wide', 'strategic', 'competitive advantage', 'innovation'],
        4: ['scale', 'automate', 'optimize', 'efficiency', 'productivity'],
        3: ['improve', 'enhance', 'implement', 'develop', 'build'],
        2: ['pilot', 'test', 'assess', 'evaluate', 'explore'],
        1: ['document', 'plan', 'research', 'study']
    }
    
    impact = 3
    for score, keywords in impact_keywords.items():
        if any(kw in text_lower for kw in keywords):
            impact = score
            break
    
    # ROI score based on value generation keywords
    roi_keywords = {
        5: ['cost reduction', 'revenue growth', 'profit', 'savings', 'monetize'],
        4: ['efficiency', 'productivity', 'reduce costs', 'increase revenue', 'roi'],
        3: ['streamline', 'optimize', 'improve', 'performance'],
        2: ['training', 'capability', 'foundation', 'infrastructure'],
        1: ['governance', 'compliance', 'policy', 'framework']
    }
    
    roi = 3
    for score, keywords in roi_keywords.items():
        if any(kw in text_lower for kw in keywords):
            roi = score
            break
    
    # Risk score based on uncertainty and change management keywords
    risk_keywords = {
        5: ['legacy', 'migration', 'transformation', 'restructure', 'overhaul'],
        4: ['integration', 'cross-functional', 'enterprise-wide', 'regulatory', 'compliance'],
        3: ['deploy', 'implement', 'scale', 'automate', 'ml', 'machine learning'],
        2: ['pilot', 'test', 'evaluate', 'enhance', 'improve'],
        1: ['document', 'plan', 'research', 'train', 'workshop']
    }
    
    risk = 3
    for score, keywords in risk_keywords.items():
        if any(kw in text_lower for kw in keywords):
            risk = score
            break
    
    # Complexity score based on implementation difficulty
    complexity_keywords = {
        5: ['integration', 'legacy', 'cross-functional', 'enterprise', 'migration', 'infrastructure'],
        4: ['data pipeline', 'platform', 'architecture', 'ml model', 'predictive', 'analytics'],
        3: ['deploy', 'implement', 'develop', 'build', 'automate', 'chatbot'],
        2: ['configure', 'customize', 'extend', 'enhance', 'dashboard'],
        1: ['enable', 'activate', 'setup', 'basic', 'training', 'workshop']
    }
    
    complexity = 3
    for score, keywords in complexity_keywords.items():
        if any(kw in text_lower for kw in keywords):
            complexity = score
            break
    
    # Determine dependencies based on initiative type and phase
    dependencies = []
    
    if any(kw in text_lower for kw in ['data pipeline', 'analytics', 'ml', 'machine learning', 'predictive']):
        dependencies.append("Data Infrastructure")
    if any(kw in text_lower for kw in ['automate', 'automation', 'workflow']):
        dependencies.append("Process Documentation")
    if any(kw in text_lower for kw in ['deploy', 'scale', 'enterprise']):
        dependencies.append("AI Governance Framework")
    if any(kw in text_lower for kw in ['chatbot', 'customer service', 'support']):
        dependencies.append("Knowledge Base Setup")
    if any(kw in text_lower for kw in ['recommendation', 'personalization', 'customer insights']):
        dependencies.append("Customer Data Platform")
    if any(kw in text_lower for kw in ['inventory', 'supply chain', 'forecasting']):
        dependencies.append("Historical Data Collection")
    
    if phase == "Growth":
        dependencies.append("Foundation Phase Completion")
    elif phase == "Optimization":
        dependencies.append("Growth Phase Metrics")
    
    dependencies = list(dict.fromkeys(dependencies))[:4]
    if not dependencies:
        dependencies = ["None - Can start immediately"]
    
    # Calculate priority based on impact, ROI, and complexity
    priority_score = (impact * 0.4) + (roi * 0.4) - (complexity * 0.2)
    
    if priority_score >= 3.0:
        priority = "High Priority"
    elif priority_score >= 2.0:
        priority = "Medium Priority"
    else:
        priority = "Low Priority"
    
    # Generate detailed recommendation
    avg_difficulty = (risk + complexity) / 2
    if avg_difficulty >= 4:
        recommendation = "High-effort initiative. Ensure dedicated resources, executive sponsorship, and phased rollout plan."
    elif avg_difficulty >= 3:
        recommendation = "Moderate complexity. Assign cross-functional team and establish clear milestones."
    elif avg_difficulty >= 2:
        recommendation = "Manageable scope. Good candidate for quick wins with existing team capacity."
    else:
        recommendation = "Low barrier to entry. Ideal for building momentum and demonstrating early AI value."
    
    return {
        "impact": impact,
        "roi": roi,
        "risk": risk,
        "complexity": complexity,
        "dependencies": dependencies,
        "priority": priority,
        "recommendation": recommendation
    }


def parse_roadmap_initiatives(roadmap_text):
    """
    Parse roadmap text to extract individual initiatives and score them.
    Returns list of initiative dicts with name, description, phase, and scores.
    Handles multiple formats: bullet points, numbered items, and **Initiative Name:** format.
    """
    initiatives = []
    current_phase = ""
    current_initiative_name = None
    current_description = ""
    
    lines = roadmap_text.split('\n')
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Detect phase headers
        if 'phase 1' in line_lower or 'short-term' in line_lower:
            current_phase = "Foundation"
        elif 'phase 2' in line_lower or 'medium-term' in line_lower:
            current_phase = "Growth"
        elif 'phase 3' in line_lower or 'long-term' in line_lower:
            current_phase = "Optimization"
        
        # Pattern 1: **Initiative Name:** format (common in GPT output)
        initiative_match = re.match(r'\*\*Initiative Name:\*\*\s*(.+)', line_stripped, re.IGNORECASE)
        if initiative_match:
            # Save previous initiative if exists
            if current_initiative_name:
                scores = score_ai_initiative(current_description or current_initiative_name, current_phase)
                initiatives.append({
                    "name": current_initiative_name,
                    "description": current_description or current_initiative_name,
                    "phase": current_phase or "General",
                    **scores
                })
            current_initiative_name = initiative_match.group(1).strip()
            current_description = ""
            continue
        
        # Pattern 2: **Description:** line - capture the description
        desc_match = re.match(r'[-*•]?\s*\*\*Description:\*\*\s*(.+)', line_stripped, re.IGNORECASE)
        if desc_match and current_initiative_name:
            current_description = desc_match.group(1).strip()
            continue
        
        # Pattern 3: Bullet points or numbered items (fallback)
        if line_stripped.startswith(('-', '•')) or re.match(r'^\d+\.', line_stripped):
            # Skip if it's a description or priority line
            if 'description:' in line_lower or 'priority:' in line_lower:
                continue
            
            # Clean up the line
            name = re.sub(r'^[-*•\d.]+\s*', '', line_stripped).strip()
            # Remove bold markers
            name = re.sub(r'\*\*([^*]+)\*\*', r'\1', name)
            
            if len(name) > 10 and 'initiative' not in name.lower():
                scores = score_ai_initiative(name, current_phase)
                initiatives.append({
                    "name": name,
                    "description": name,
                    "phase": current_phase or "General",
                    **scores
                })
    
    # Don't forget the last initiative
    if current_initiative_name:
        scores = score_ai_initiative(current_description or current_initiative_name, current_phase)
        initiatives.append({
            "name": current_initiative_name,
            "description": current_description or current_initiative_name,
            "phase": current_phase or "General",
            **scores
        })
    
    return initiatives


def inject_scores_into_html(roadmap_html, initiatives):
    """
    Inject scoring tags directly after each initiative in the roadmap HTML.
    Uses BeautifulSoup for proper HTML parsing and manipulation.
    Returns modified HTML with analysis tags appended after matching elements.
    """
    from bs4 import BeautifulSoup
    import logging
    
    if not initiatives:
        return roadmap_html
    
    soup = BeautifulSoup(roadmap_html, 'html.parser')
    
    # Track which initiatives have been matched to avoid duplicates
    matched_initiatives = set()
    
    # Find all paragraph elements - initiatives typically appear as <p><strong>Initiative Name:</strong> Name</p>
    all_paragraphs = soup.find_all('p')
    
    for p_element in all_paragraphs:
        p_text = p_element.get_text().lower().strip()
        
        # Skip empty or very short paragraphs
        if len(p_text) < 10:
            continue
        
        # Try to match this paragraph to an initiative
        for idx, item in enumerate(initiatives):
            if idx in matched_initiatives:
                continue
            
            # Check if initiative name appears in the paragraph text
            name_lower = item['name'].lower().strip()
            
            # Match if the initiative name is contained in the paragraph
            if name_lower in p_text or (len(name_lower) > 10 and name_lower[:20] in p_text):
                matched_initiatives.add(idx)
                logging.debug(f"Matched initiative: {item['name']}")
                
                # Create inline score tag with Impact, ROI, Complexity, Recommendation
                score_div = soup.new_tag('div')
                score_div['style'] = "background: #f9fafb; padding: 8px 12px; border-radius: 6px; margin-top: 8px; font-size: 12px; display: flex; flex-wrap: wrap; gap: 12px; border: 1px solid #e5e7eb;"
                
                # Impact
                impact_span = soup.new_tag('span', style="color: #1d4ed8; font-weight: 500;")
                impact_span.string = f"Impact: {item.get('impact', 3)}/5"
                score_div.append(impact_span)
                
                # ROI
                roi_span = soup.new_tag('span', style="color: #15803d; font-weight: 500;")
                roi_span.string = f"ROI: {item.get('roi', 3)}/5"
                score_div.append(roi_span)
                
                # Complexity
                complexity_span = soup.new_tag('span', style="color: #7c3aed; font-weight: 500;")
                complexity_span.string = f"Complexity: {item['complexity']}/5"
                score_div.append(complexity_span)
                
                # Priority/Recommendation
                priority = item.get('priority', 'Medium Priority')
                if priority == 'High Priority':
                    priority_style = "color: #b91c1c; background: #fef2f2;"
                elif priority == 'Medium Priority':
                    priority_style = "color: #b45309; background: #fffbeb;"
                else:
                    priority_style = "color: #4b5563; background: #f9fafb;"
                
                priority_span = soup.new_tag('span', style=f"{priority_style} font-weight: 600; padding: 2px 8px; border-radius: 4px;")
                priority_span.string = f"Recommendation: {priority}"
                score_div.append(priority_span)
                
                # Insert score div after the paragraph element
                p_element.insert_after(score_div)
                break
    
    return str(soup)


@app.route("/roadmap/<int:roadmap_id>")
def view_roadmap(roadmap_id):
    """View a specific generated roadmap."""
    roadmap = RoadmapGeneration.query.get_or_404(roadmap_id)
    goals_list = [g.strip() for g in roadmap.goals.split(",")]
    
    # Calculate AI Maturity Score
    maturity_score = calculate_maturity_score(roadmap.ai_maturity, goals_list)
    industry_average, percentile = get_industry_benchmark(roadmap.industry, maturity_score)
    
    # Parse and score initiatives from roadmap content
    initiatives = parse_roadmap_initiatives(roadmap.roadmap_content or "")
    
    # Convert roadmap markdown to HTML and inject scoring tags
    roadmap_html = render_markdown(roadmap.roadmap_content)
    roadmap_with_scores = inject_scores_into_html(roadmap_html, initiatives)
    
    return render_template(
        "results.html",
        roadmap_id=roadmap.id,
        organization_name=roadmap.organization_name or "N/A",
        organization_size=roadmap.organization_size,
        industry=roadmap.industry,
        ai_maturity=roadmap.ai_maturity,
        goals=goals_list,
        roadmap=roadmap_with_scores,
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
                <li>Risk and complexity analysis</li>
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
