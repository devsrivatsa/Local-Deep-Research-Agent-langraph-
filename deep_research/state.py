from typing import Annotated, List, TypedDict, Literal
from pydantic import BaseModel, Field
import operator

class SearchQuery(BaseModel):
    search_query: str = Field(description="Search query for the report")

class Queries(BaseModel):
    queries: List[SearchQuery] = Field(description="List of search queries for the report")

class Section(BaseModel):
    name: str = Field(description="Name for this section of the report")
    description: str = Field(description="Description of the main topics and concepts covered in this section")
    research: bool = Field(description="Whether this section is research or not")
    content: str = Field(description="Content for this section of the report")

class Sections(BaseModel):
    sections: List[Section] = Field(description="List of sections for the report")

class SectionState(TypedDict):
    topic: str
    section: Section
    search_iterations: int = Field(default=0, description="The number of search iterations performed for this section")
    search_queries: List[SearchQuery] = Field(default=[], description="The list of search queries for this section")
    source_str: str = Field(description="The source string or the formatter source content from the web search for this section")
    report_sections_from_research: str = Field(description="Any completed sections from research to write final sections")
    completed_sections: List[Section]

class SectionOutputState(TypedDict):
    completed_sections: list[Section]


class Feedback(BaseModel):
    grade: Literal["pass", "fail"] = Field(
        description="Evaluation result indicating whether the response meets requirements ('pass') or needs revision ('fail')."
    )
    follow_up_queries: List[SearchQuery] = Field(
        description="List of follow-up search queries."
    )

class ReportStateInput(TypedDict):
    topic: str

class ReportStateOutput(TypedDict):
    final_report: str

class ReportState(TypedDict):
    topic: str
    feedback_on_report_plan: str
    sections: List[Section]
    completed_sections: Annotated[list, operator.add] = Field(default=[], description="List of completed sections")
    report_sections_from_research: str
    final_report: str

