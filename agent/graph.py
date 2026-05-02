"""
graph.py
========
LangGraph multi-agent graph wiring.
Connects the supervisor agent with forecasting and geospatial tools.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent  

load_dotenv(Path(__file__).parent / ".env")

from agents.forecasting import forecast_crime
from agents.geospatial import crimes_by_area, crimes_by_radius
from datetime import date

tools = [forecast_crime, crimes_by_area, crimes_by_radius]

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)



agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=(
        f"Today's date is {date.today().isoformat()}. You are a crime analysis assistant for the Chicago Police Department. "
        "You have access to tools that query a PostGIS crime database and a "
        "forecasting model trained on 1.5M historical crime records.\n\n"
        "When answering questions:\n"
        "1. Use forecast_crime to get predicted crime counts for future dates\n"
        "2. Use crimes_by_area to get historical crime stats for an area\n"
        "3. Use crimes_by_radius to get recent crimes near a specific location\n"
        "4. Always cite the data source in your answer\n"
        "5. Be specific — include numbers, dates, and area codes\n"
        "Community area codes: Austin=25, Loop=32, Hyde Park=41"
    ),
)


def run(question: str) -> str:
    """Run the agent with a natural language question."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "What is the forecast for Austin community area next Saturday?"
    print(run(q))