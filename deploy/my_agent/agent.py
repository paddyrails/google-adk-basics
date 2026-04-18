"""Production agent definition."""
from google.adk.agents import LlmAgent

def get_current_time(city: str) -> dict:
    """Returns the current time for a city.

    Args:
        city: City name.
    """
    import datetime
    return {"city": city, "time": datetime.datetime.now().isoformat(), "timezone": "UTC"}

def get_weather(city: str) -> dict:
    """Returns weather for a city.

    Args:
        city: City name.
    """
    return {"city": city, "temp": "22C", "condition": "Sunny"}

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="assistant",
    description="A helpful assistant that can tell time and weather",
    instruction="""You are a helpful assistant. You can:
1. Tell the current time using get_current_time
2. Check weather using get_weather
Be concise.""",
    tools=[get_current_time, get_weather],
)
