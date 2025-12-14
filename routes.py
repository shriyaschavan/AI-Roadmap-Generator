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
    Uses multi-pass parsing with fallback strategies.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    initiatives = []
    current_phase = "Short-term (0-6 months)"
    
    if not roadmap_text:
        logger.debug("parse_roadmap_initiatives: No roadmap text provided")
        return initiatives
    
    lines = roadmap_text.split('\n')
    current_initiative = None
    logger.debug(f"parse_roadmap_initiatives: Processing {len(lines)} lines")
    
    # Skip labels that aren't initiative titles
    skip_labels = ['initiative name', 'description', 'priority', 'phase', 'timeline', 
                   'kpi', 'metric', 'overview', 'summary', 'introduction', 'conclusion',
                   'objective', 'goal', 'target', 'expected outcome', 'key results']
    
    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Detect phase headers (multiple patterns)
        if 'phase 1' in line_lower or 'short-term' in line_lower or '0-6 month' in line_lower or '0 - 6 month' in line_lower:
            current_phase = "Short-term (0-6 months)"
        elif 'phase 2' in line_lower or 'medium-term' in line_lower or '6-12 month' in line_lower or '6 - 12 month' in line_lower:
            current_phase = "Medium-term (6-12 months)"
        elif 'phase 3' in line_lower or 'long-term' in line_lower or '12-24 month' in line_lower or '12 - 24 month' in line_lower:
            current_phase = "Long-term (12-24 months)"
        
        # Pattern 0: ### Initiative N: Title (H3 header with initiative number)
        match = re.match(r'^#{1,3}\s*Initiative\s*\d+\s*:\s*(.+)', line_stripped, re.IGNORECASE)
        if match:
            if current_initiative and current_initiative.get('title'):
                initiatives.append(current_initiative)
            current_initiative = {
                'title': match.group(1).strip(),
                'description': '',
                'phase': current_phase
            }
            continue
        
        # Pattern 1: 1. **Initiative Name**: Title (numbered, colon outside bold)
        match = re.match(r'^\d+\.\s*\*\*Initiative\s*Name\*\*\s*:\s*(.+)', line_stripped, re.IGNORECASE)
        if match:
            if current_initiative and current_initiative.get('title'):
                initiatives.append(current_initiative)
            current_initiative = {
                'title': match.group(1).strip(),
                'description': '',
                'phase': current_phase
            }
            continue
        
        # Pattern 2: **Initiative Name:** Title (colon inside bold)
        match = re.match(r'^[\d.]*\s*\*\*Initiative\s*Name:\*\*\s*(.+)', line_stripped, re.IGNORECASE)
        if match:
            if current_initiative and current_initiative.get('title'):
                initiatives.append(current_initiative)
            current_initiative = {
                'title': match.group(1).strip(),
                'description': '',
                'phase': current_phase
            }
            continue
        
        # Pattern 3: - **Description**: text (colon outside bold)
        match = re.match(r'^[-*•]\s*\*\*Description\*\*\s*:\s*(.+)', line_stripped, re.IGNORECASE)
        if match and current_initiative:
            current_initiative['description'] = match.group(1).strip()
            continue
        
        # Pattern 4: - **Description:** text (colon inside bold)
        match = re.match(r'^[-*•]\s*\*\*Description:\*\*\s*(.+)', line_stripped, re.IGNORECASE)
        if match and current_initiative:
            current_initiative['description'] = match.group(1).strip()
            continue
        
        # Pattern 5: ### Bold Header (H3 headers as initiatives)
        match = re.match(r'^###\s+(.+)', line_stripped)
        if match:
            title = match.group(1).strip()
            title = re.sub(r'\*\*(.+)\*\*', r'\1', title)  # Remove bold markers
            if title.lower() not in skip_labels and len(title) > 3:
                if current_initiative and current_initiative.get('title'):
                    initiatives.append(current_initiative)
                current_initiative = {
                    'title': title,
                    'description': '',
                    'phase': current_phase
                }
                continue
        
        # Pattern 6: Numbered items with bold: 1. **Title** or 1. **Title**: desc
        match = re.match(r'^\d+\.\s*\*\*([^*]+)\*\*\s*:?\s*(.*)$', line_stripped)
        if match:
            title = match.group(1).strip()
            if title.lower() not in skip_labels and len(title) > 3:
                if current_initiative and current_initiative.get('title'):
                    initiatives.append(current_initiative)
                desc = match.group(2).strip() if match.group(2) else ''
                current_initiative = {
                    'title': title,
                    'description': desc,
                    'phase': current_phase
                }
                continue
        
        # Pattern 7: Generic bold bullet - **Title**: description or - **Title**
        match = re.match(r'^[-•*]\s*\*\*([^*:]+)\*\*\s*:?\s*(.*)$', line_stripped)
        if match:
            title = match.group(1).strip()
            if title.lower() not in skip_labels and len(title) > 3:
                if current_initiative and current_initiative.get('title'):
                    initiatives.append(current_initiative)
                desc = match.group(2).strip() if match.group(2) else ''
                current_initiative = {
                    'title': title,
                    'description': desc,
                    'phase': current_phase
                }
                continue
    
    # Add the last initiative
    if current_initiative and current_initiative.get('title'):
        initiatives.append(current_initiative)
    
    # FALLBACK: If no initiatives found, try more aggressive parsing
    if not initiatives:
        logger.debug("parse_roadmap_initiatives: Primary parsing found 0 initiatives, trying fallback")
        initiatives = _fallback_parse_initiatives(roadmap_text, skip_labels)
    
    logger.debug(f"parse_roadmap_initiatives: Found {len(initiatives)} initiatives")
    for i, init in enumerate(initiatives):
        logger.debug(f"  Initiative {i+1}: {init['title'][:50]}...")
    
    return initiatives


def _fallback_parse_initiatives(roadmap_text, skip_labels):
    """
    Fallback parser for legacy formats. Extracts any bold text or numbered items
    that look like initiative titles.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    initiatives = []
    current_phase = "Short-term (0-6 months)"
    lines = roadmap_text.split('\n')
    
    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Update phase
        if 'phase 1' in line_lower or 'short' in line_lower:
            current_phase = "Short-term (0-6 months)"
        elif 'phase 2' in line_lower or 'medium' in line_lower:
            current_phase = "Medium-term (6-12 months)"
        elif 'phase 3' in line_lower or 'long' in line_lower:
            current_phase = "Long-term (12-24 months)"
        
        # Find any bold text that might be an initiative
        bold_matches = re.findall(r'\*\*([^*]+)\*\*', line_stripped)
        for bold in bold_matches:
            title = bold.strip()
            if title.lower() not in skip_labels and len(title) > 5 and len(title) < 100:
                # Avoid duplicates
                if not any(init['title'] == title for init in initiatives):
                    initiatives.append({
                        'title': title,
                        'description': '',
                        'phase': current_phase
                    })
        
        # Find numbered items without bold
        if not bold_matches:
            match = re.match(r'^\d+\.\s+([A-Z][^.]+)', line_stripped)
            if match:
                title = match.group(1).strip()
                if title.lower() not in skip_labels and len(title) > 5 and len(title) < 100:
                    if not any(init['title'] == title for init in initiatives):
                        initiatives.append({
                            'title': title,
                            'description': '',
                            'phase': current_phase
                        })
    
    logger.debug(f"_fallback_parse_initiatives: Found {len(initiatives)} initiatives")
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
    """
    import logging
    logger = logging.getLogger(__name__)
    from bs4 import BeautifulSoup
    
    # Parse initiatives from text
    initiatives = parse_roadmap_initiatives(roadmap_text)
    
    logger.debug(f"inject_scores_into_html: Found {len(initiatives)} initiatives to inject")
    
    if not initiatives:
        logger.debug("inject_scores_into_html: No initiatives found, returning original HTML")
        return roadmap_html
    
    soup = BeautifulSoup(roadmap_html, 'html.parser')
    injected_titles = set()
    
    # Find all list items and H3 headers - initiatives can be in either
    all_lis = soup.find_all('li')
    all_h3s = soup.find_all('h3')
    all_elements = all_lis + all_h3s
    logger.debug(f"inject_scores_into_html: Found {len(all_lis)} list items and {len(all_h3s)} H3 headers in HTML")
    
    for init in initiatives:
        title = init['title']
        title_lower = title.lower()
        
        if title in injected_titles:
            continue
            
        scores = score_ai_initiative(title, init.get('description', ''))
        deps_text = ', '.join(scores['dependencies']) if scores['dependencies'] else 'None'
        
        score_html = f'''
<div class="initiative-meta" style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-left: 4px solid #9ca3af; border-radius: 8px; padding: 12px; margin-top: 8px; font-size: 14px; color: #374151;">
    <div style="margin-bottom: 4px;"><strong>Risk:</strong> {scores['risk']}/5</div>
    <div style="margin-bottom: 4px;"><strong>Complexity:</strong> {scores['complexity']}/5</div>
    <div style="margin-bottom: 4px;"><strong>Dependencies:</strong> {deps_text}</div>
    <div><strong>Recommendation:</strong> {scores['recommendation']}</div>
</div>
'''
        
        # Find the element containing this initiative's title
        matched = False
        for elem in all_elements:
            elem_text = elem.get_text()
            # Check if this element contains the initiative title
            if title_lower in elem_text.lower():
                # Make sure we haven't already injected here
                existing_meta = elem.find('div', class_='initiative-meta')
                if not existing_meta:
                    # For H3 tags, insert after instead of appending inside
                    if elem.name == 'h3':
                        elem.insert_after(BeautifulSoup(score_html, 'html.parser'))
                    else:
                        elem.append(BeautifulSoup(score_html, 'html.parser'))
                    injected_titles.add(title)
                    matched = True
                    logger.debug(f"inject_scores_into_html: Injected scores for '{title[:40]}...'")
                    break
        
        if not matched:
            logger.debug(f"inject_scores_into_html: Could NOT find match for '{title[:40]}...'")
    
    logger.debug(f"inject_scores_into_html: Successfully injected {len(injected_titles)} scoring blocks")
    return str(soup)


def sanitize_mermaid_chart(chart_text):
    """
    Sanitize mermaid chart to fix syntax issues.
    - Removes leading/trailing whitespace
    - Converts tabs to spaces
    - Removes HTML-escaped characters
    - Replaces colons in task names with dashes
    - Fixes missing commas in task definitions
    """
    if not chart_text:
        return chart_text
    
    # Remove leading/trailing whitespace
    chart_text = chart_text.strip()
    
    # Convert tabs to 4 spaces
    chart_text = chart_text.replace('\t', '    ')
    
    # Remove HTML-escaped characters
    chart_text = chart_text.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
    chart_text = chart_text.replace('&quot;', '"').replace('&#39;', "'")
    
    lines = chart_text.split('\n')
    sanitized_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            continue
        
        # Check if this is a task line (contains :done, :active, or :des followed by number)
        task_pattern = re.search(r':(done|active|des\d+)', stripped)
        if task_pattern:
            # Fix missing commas after status markers: ":des5 2025" -> ":des5, 2025"
            stripped = re.sub(r':(done|active|des\d+)\s+(\d{4})', r':\1, \2', stripped)
            
            # Find the position of the status marker and sanitize only the task name (before it)
            match = re.search(r'\s*:(done|active|des\d+)', stripped)
            if match:
                task_name = stripped[:match.start()]
                rest = stripped[match.start():]
                # Replace colons in task name with dashes
                task_name = task_name.replace(':', ' -')
                stripped = task_name + rest
        
        # Add proper indentation for task lines (4 spaces for tasks under sections)
        if stripped.startswith('gantt') or stripped.startswith('dateFormat') or stripped.startswith('title') or stripped.startswith('section') or stripped.startswith('%%'):
            sanitized_lines.append(stripped)
        else:
            sanitized_lines.append('    ' + stripped)
    
    return '\n'.join(sanitized_lines)


def is_mermaid_valid(chart_text):
    """
    Check if mermaid chart has valid basic structure.
    Returns True if chart appears to be valid gantt syntax.
    """
    if not chart_text:
        return False
    chart_lower = chart_text.lower()
    return 'gantt' in chart_lower and ':' in chart_text


def get_fallback_mermaid_chart():
    """
    Return a fallback mermaid chart when the original is invalid.
    """
    return """gantt
    dateFormat  YYYY-MM-DD
    title AI Implementation Timeline
    section Phase 1
    Foundation Setup :done, des1, 2024-01-01, 180d
    section Phase 2
    Growth Initiative :active, des2, after des1, 180d
    section Phase 3
    Optimization :des3, after des2, 365d"""


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
    
    # Assign KPIs and scores to each initiative with defensive defaults
    for initiative in initiatives:
        kpis = assign_kpis(initiative, industry=roadmap.industry, goals=goals_list) or {}
        # Ensure all KPI fields have safe defaults
        initiative['kpis'] = {
            'primary_kpis': kpis.get('primary_kpis') or ['Outcome Metric'],
            'secondary_kpis': kpis.get('secondary_kpis') or ['Adoption Rate'],
            'baseline': kpis.get('baseline') or 'Current State',
            'target': kpis.get('target') or 'Target State',
            'value_driver': kpis.get('value_driver') or 'Value Realization',
            'measurement_frequency': kpis.get('measurement_frequency') or 'Monthly',
            'data_sources': kpis.get('data_sources') or ['Operational Systems']
        }
        scores = score_ai_initiative(initiative['title'], initiative.get('description', '')) or {}
        initiative['impact'] = scores.get('impact', 3)
        initiative['roi'] = scores.get('roi', 3)
        initiative['complexity'] = scores.get('complexity', 3)
        initiative['priority'] = scores.get('priority', 'Medium Priority')
    
    # Render markdown and inject scoring tags
    roadmap_html = render_markdown(roadmap.roadmap_content)
    roadmap_html_with_scores = inject_scores_into_html(roadmap_html, roadmap.roadmap_content or "")
    
    # Sanitize and validate mermaid chart with fallback
    mermaid_chart = sanitize_mermaid_chart(roadmap.mermaid_chart)
    if not is_mermaid_valid(mermaid_chart):
        mermaid_chart = get_fallback_mermaid_chart()
    
    return render_template(
        "results.html",
        roadmap_id=roadmap.id,
        organization_name=roadmap.organization_name or "N/A",
        organization_size=roadmap.organization_size,
        industry=roadmap.industry,
        ai_maturity=roadmap.ai_maturity,
        goals=goals_list,
        roadmap=roadmap_html_with_scores,
        mermaid_chart=mermaid_chart,
        created_at=roadmap.created_at,
        maturity_score=maturity_score,
        industry_average=industry_average,
        percentile=percentile,
        initiatives=initiatives,
        debug_mermaid=False
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
