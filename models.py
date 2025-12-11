from app import db
from datetime import datetime


class RoadmapGeneration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_size = db.Column(db.String(50), nullable=False)
    industry = db.Column(db.String(200), nullable=False)
    ai_maturity = db.Column(db.String(50), nullable=False)
    goals = db.Column(db.Text, nullable=False)
    roadmap_content = db.Column(db.Text, nullable=True)
    mermaid_chart = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
