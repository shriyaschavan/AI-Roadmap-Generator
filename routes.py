from flask import render_template, request, flash, redirect, url_for
from app import app, db
from models import RoadmapGeneration
from openai_service import generate_roadmap


@app.route("/")
def index():
    """Display the input form for roadmap generation."""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """Process form submission and generate AI roadmap."""
    organization_size = request.form.get("organization_size", "").strip()
    industry = request.form.get("industry", "").strip()
    ai_maturity = request.form.get("ai_maturity", "").strip()
    goals = request.form.getlist("goals")
    
    if not organization_size or not industry or not ai_maturity:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("index"))
    
    if not goals:
        flash("Please select at least one goal.", "error")
        return redirect(url_for("index"))
    
    result = generate_roadmap(organization_size, industry, ai_maturity, goals)
    
    if not result["success"]:
        flash(f"Failed to generate roadmap: {result['error']}", "error")
        return redirect(url_for("index"))
    
    generation = RoadmapGeneration(
        organization_size=organization_size,
        industry=industry,
        ai_maturity=ai_maturity,
        goals=", ".join(goals),
        roadmap_content=result["roadmap"],
        mermaid_chart=result["mermaid_chart"]
    )
    db.session.add(generation)
    db.session.commit()
    
    return render_template(
        "results.html",
        organization_size=organization_size,
        industry=industry,
        ai_maturity=ai_maturity,
        goals=goals,
        roadmap=result["roadmap"],
        mermaid_chart=result["mermaid_chart"]
    )
