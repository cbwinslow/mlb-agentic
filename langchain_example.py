from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model


class BootstrapRequest(BaseModel):
    mode: str = Field(description="Either 'job_ids' or 'profile'")
    job_ids: list[str] = Field(default_factory=list, description="Approved job IDs")
    profile: str | None = Field(default=None, description="Approved profile name")
    variables: dict[str, str] = Field(default_factory=dict, description="Runtime variable overrides")


model = init_chat_model("openai:gpt-4.1-mini")
structured = model.with_structured_output(BootstrapRequest)

prompt = """
Return a bootstrap request for historical MLB ingestion.
Use profile historical_plus_statcast.
Set DATA_ROOT to /srv/mlb-data.
Set PROJECT_ROOT to /srv/mlb-baseball-ml.
Set START_DATE to 2015-01-01.
Set END_DATE to 2026-12-31.
Do not add extra keys.
"""

result = structured.invoke(prompt)
print(result.model_dump())
