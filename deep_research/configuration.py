from dataclasses import dataclass, Field, fields
from langchain_core.runnables import RunnableConfig
from enum import Enum
from typing import Optional, Any, Dict
import os

DEFAULT_REPORT_STRUCTURE = """Use this structure to create a report on the user-provided topic:
1.Introduction (no research needed)
    - Brief overview of the topic area

2. Main Body Sections:
    - Each section should focus on a sub-topic of the user-provided topic

3. Conclusion
    - Aim for 1 structural element (either a list of a table) that distills the main body sections
    - Provide a concise summary of the report
"""

class SearchAPI(Enum):
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"
    EXA = "exa"
    ARXIV = "arxiv"
    PUBMED = "pubmed"
    LINKUP = "linkup"
    DUCKDUCKGO = "duckduckgo"
    GOOGLESEARCH = "googlesearch"

@dataclass(kw_only=True)
class Configuration:
    """The configurable fields for the chatbot"""
    report_structure: str = DEFAULT_REPORT_STRUCTURE
    number_of_queries: int = Field(default=2, description="The number of queries to generate per iteration")
    max_search_depth: int = Field(default=2, description="The maximum number of reflections + search iterations to perform")
    planner_provider: str = Field(default="anthropic", description="The provider to use for the planner")
    planner_model: str = Field(default="claude-3-7-sonnet-latest", description="The model to use for the planner")
    writer_provider: str = Field(default="anthropic", description="The provider to use for the writer")
    writer_model: str = Field(default="claude-3-7-sonnet-latest", description="The model to use for the writer")
    search_api: SearchAPI = Field(default=SearchAPI.TAVILY, description="The search API to use")
    search_api_config: Optional[Dict[str, Any]] = Field(default=None, description="The configuration for the search API")

    @classmethod
    def from_runnable_config(cls, config: Optional[RunnableConfig]) -> "Configuration":
        """Create a Configuration from a RunnableConfig"""
        configurable = (config["configurable"] if config else {})
        values: Dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls)
            if f.init
        }

        return cls(**{k:v for k,v in values.items() if v is not None})