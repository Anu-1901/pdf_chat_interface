import os
import httpx
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()

# Config from .env
CONFIG = {
    "base_url": os.getenv("FARM_BASE_URL"),
    "api_key": os.getenv("FARM_API_KEY"),
    "deployment": os.getenv("FARM_DEPLOYMENT_NAME"),
    "api_version": os.getenv("FARM_API_VERSION"),
}

# Validate
missing = [k for k, v in CONFIG.items() if not v]
if missing:
    raise ValueError(f"Missing .env values: {missing}")

# Create HTTP client with Bosch Farm header
http_client = httpx.Client(headers={"genaiplatform-farm-subscription-key": CONFIG["api_key"]})

# Create LangChain LLM
llm = AzureChatOpenAI(
    api_key=CONFIG["api_key"],
    azure_endpoint=CONFIG["base_url"],
    azure_deployment=CONFIG["deployment"],
    api_version=CONFIG["api_version"],
    http_client=http_client,
    temperature=0,
)

print("✓ LLM ready")
question = "Hello, world!"

response = llm.invoke(question)

print("Question:", question)
print("Answer:", response.content)