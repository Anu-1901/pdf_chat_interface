---
description: Standard instructions for coding assistants to configure
  and invoke Bosch LLM Farm chat models in Python using LangChain
  AzureChatOpenAI.
name: bosch-llm-farm
---

# Bosch LLM Farm -- Standard Skill

Use this skill whenever Python code needs to call a chat model through
Bosch LLM Farm.

## Configuration

Read credentials and deployment settings from `.env`. Never hard-code or
print secrets.

``` dotenv
MODEL_NAME="gpt-4o-mini"
FARM_BASE_URL="https://aoai-farm.bosch-temp.com/api"
FARM_API_KEY=""
FARM_DEPLOYMENT_NAME="askbosch-prod-farm-openai-gpt-4o-mini-2024-07-18"
FARM_API_VERSION="2023-12-01-preview"
EMBEDDING_DEPLOYMENT_NAME="askbosch-prod-farm-openai-text-embedding-3-small"
EMBEDDING_API_VERSION="2024-10-21"
```

Keep `.env` out of version control by adding it to `.gitignore`.
Populate `FARM_API_KEY` locally using the approved Bosch credential
source. The embedding settings are for embedding integrations; they are
not required for chat invocation.

## Dependencies

``` bash
pip install langchain-openai httpx python-dotenv
```

## Standard implementation

Use this integration pattern. Do not replace the Bosch Farm endpoint or
authentication header with a direct OpenAI endpoint.

``` python
import os
import httpx
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()

required = {
    "FARM_BASE_URL": os.getenv("FARM_BASE_URL"),
    "FARM_API_KEY": os.getenv("FARM_API_KEY"),
    "FARM_DEPLOYMENT_NAME": os.getenv("FARM_DEPLOYMENT_NAME"),
    "FARM_API_VERSION": os.getenv("FARM_API_VERSION"),
}
missing = [key for key, value in required.items() if not value]
if missing:
    raise ValueError(f"Missing .env values: {', '.join(missing)}")

http_client = httpx.Client(
    headers={
        "genaiplatform-farm-subscription-key": required["FARM_API_KEY"]
    },
    timeout=60.0,
)

llm = AzureChatOpenAI(
    api_key=required["FARM_API_KEY"],
    azure_endpoint=required["FARM_BASE_URL"],
    azure_deployment=required["FARM_DEPLOYMENT_NAME"],
    api_version=required["FARM_API_VERSION"],
    http_client=http_client,
    temperature=0,
)

# Invoke the model
response = llm.invoke("Hello, world!")
print(response.content)
```

## Rules for coding assistants

-   Use `AzureChatOpenAI` with the Bosch Farm endpoint, deployment, and
    API version from environment variables.
-   Include the `genaiplatform-farm-subscription-key` header in the
    `httpx.Client`.
-   Validate required configuration before creating the model.
-   Initialize the client once and reuse it; do not recreate it for
    every request.
-   Keep `.env` and API keys out of source control, logs, prompts, and
    generated output.
-   Do not guess or silently change endpoint, deployment, API version,
    or authentication settings.
-   If invocation fails, report the error and verify the Bosch Farm
    configuration and access before changing the integration.
