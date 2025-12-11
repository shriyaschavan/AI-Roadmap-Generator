import os
import re
from openai import OpenAI

# Using gpt-4o model for chat completions
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = None

def get_client():
    global client
    if client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key)
    return client

SYSTEM_PROMPT = """You are an enterprise AI transformation consultant. Based on the user's inputs, generate a structured AI Implementation Roadmap with three phases:
Phase 1: Short-term (0–6 months)
Phase 2: Medium-term (6–12 months)
Phase 3: Long-term (12–24 months)

For each phase, include:
- Initiative name
- Description
- Priority (High/Medium/Low)

At the end, include a Mermaid.js Gantt chart. Use this exact format:

```mermaid
gantt
    title AI Roadmap Timeline
    dateFormat  YYYY-MM-DD
    section Short-term
    <Initiative 1> :done, des1, 2025-01-01, 90d
    section Medium-term
    <Initiative 2> :active, des2, 2025-04-01, 120d
    section Long-term
    <Initiative 3> :des3, 2025-08-01, 180d
```

Ensure the Gantt chart reflects the initiatives you described in each phase. Use realistic initiative names and durations."""


def generate_roadmap(organization_size: str, industry: str, ai_maturity: str, goals: list) -> dict:
    """Generate AI implementation roadmap using OpenAI API."""
    goals_text = ", ".join(goals) if goals else "General AI adoption"
    
    user_prompt = f"""Please generate an AI Implementation Roadmap for the following organization:

- Organization Size: {organization_size}
- Industry: {industry}
- Current AI Maturity Level: {ai_maturity}
- Key Goals: {goals_text}

Provide a detailed roadmap with initiatives tailored to this organization's specific context and goals."""

    try:
        openai_client = get_client()
        if openai_client is None:
            return {
                "success": False,
                "error": "OpenAI API key is not configured. Please set OPENAI_API_KEY.",
                "roadmap": None,
                "mermaid_chart": None
            }
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4096
        )
        
        content = response.choices[0].message.content
        
        mermaid_match = re.search(r'```mermaid\n(.*?)```', content, re.DOTALL)
        mermaid_chart = mermaid_match.group(1).strip() if mermaid_match else None
        
        roadmap_text = re.sub(r'```mermaid\n.*?```', '', content, flags=re.DOTALL).strip()
        
        return {
            "success": True,
            "roadmap": roadmap_text,
            "mermaid_chart": mermaid_chart
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "roadmap": None,
            "mermaid_chart": None
        }
