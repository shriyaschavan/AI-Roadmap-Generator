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
    Returns dict with impact, roi, complexity scores (1-5) and priority recommendation.
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
    
    # Complexity score based on implementation difficulty
    complexity_keywords = {
        5: ['integration', 'legacy', 'cross-functional', 'enterprise', 'migration'],
        4: ['data pipeline', 'infrastructure', 'platform', 'architecture'],
        3: ['deploy', 'implement', 'develop', 'build', 'model'],
        2: ['configure', 'customize', 'extend', 'enhance'],
        1: ['enable', 'activate', 'setup', 'basic']
    }
    
    complexity = 3
    for score, keywords in complexity_keywords.items():
        if any(kw in text_lower for kw in keywords):
            complexity = score
            break
    
    # Calculate priority based on impact, ROI, and complexity
    priority_score = (impact * 0.4) + (roi * 0.4) - (complexity * 0.2)
    
    if priority_score >= 3.0:
        priority = "High Priority"
    elif priority_score >= 2.0:
        priority = "Medium Priority"
    else:
        priority = "Long-Term / Optional"
    
    return {
        "impact": impact,
        "roi": roi,
        "complexity": complexity,
        "priority": priority
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
    
    if not initiatives:
        return roadmap_html
    
    soup = BeautifulSoup(roadmap_html, 'html.parser')
    
    # Track which initiatives have been matched to avoid duplicates
    matched_initiatives = set()
    
    # Find all paragraph and list item elements that might contain initiative names
    # The format is typically: <p><strong>Initiative Name:</strong> Name Here</p>
    all_elements = soup.find_all(['p', 'li', 'strong'])
    
    for element in all_elements:
        element_text = element.get_text().lower().strip()
        
        # Try to match this element to an initiative
        for idx, item in enumerate(initiatives):
            if idx in matched_initiatives:
                continue
            
            # Check if initiative name appears in the element text
            name_lower = item['name'].lower()
            # Use first 15 chars for fuzzy matching
            if name_lower[:15] in element_text or (len(element_text) > 15 and element_text[:15] in name_lower):
                matched_initiatives.add(idx)
                
                # Create score tag
                priority_style = ""
                if item['priority'] == 'High Priority':
                    priority_style = "color: #b91c1c; background: #fef2f2;"
                elif item['priority'] == 'Medium Priority':
                    priority_style = "color: #b45309; background: #fffbeb;"
                else:
                    priority_style = "color: #4b5563; background: #f9fafb;"
                
                # Create score tag using soup.new_tag to avoid cross-document issues
                score_div = soup.new_tag('div', style="background: #f9fafb; padding: 8px 12px; border-radius: 6px; margin-top: 6px; font-size: 12px; display: flex; flex-wrap: wrap; gap: 12px; border: 1px solid #e5e7eb;")
                
                impact_span = soup.new_tag('span', style="color: #1d4ed8; font-weight: 500;")
                impact_span.string = f"Impact: {item['impact']}/5"
                score_div.append(impact_span)
                
                roi_span = soup.new_tag('span', style="color: #15803d; font-weight: 500;")
                roi_span.string = f"ROI: {item['roi']}/5"
                score_div.append(roi_span)
                
                complexity_span = soup.new_tag('span', style="color: #7c3aed; font-weight: 500;")
                complexity_span.string = f"Complexity: {item['complexity']}/5"
                score_div.append(complexity_span)
                
                priority_span = soup.new_tag('span', style=f"{priority_style} font-weight: 600; padding: 2px 8px; border-radius: 4px;")
                priority_span.string = f"Recommendation: {item['priority']}"
                score_div.append(priority_span)
                
                # Find the parent paragraph or list item to append after
                target = element
                if element.name == 'strong':
                    target = element.parent if element.parent else element
                
                # Insert score div after the target element
                target.insert_after(score_div)
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
