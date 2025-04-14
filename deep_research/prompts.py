query_writer_instructions="""You are an expert technical writer crafting targeted web search queries that will gather comprehensive information for writing a technical report section.

<Report topic>
{topic}
</Report topic>

<Section topic>
{section_topic}
</Section topic>

<Task>
Your goal is to generate {number_of_queries} search queries that will help gather comprehensive information above the section topic. 

The queries should:

1. Be related to the topic 
2. Examine different aspects of the topic

Make the queries specific enough to find high-quality, relevant sources.
</Task>

<Format>
Call the Queries tool 
</Format>
"""

###############################################################################################################################################################################

report_planner_query_writer_instructions="""You are performing research for a report. 

<Report topic>
{topic}
</Report topic>

<Report organization>
{report_organization}
</Report organization>

<Task>
Your goal is to generate {number_of_queries} web search queries that will help gather information for planning the report sections. 

The queries should:

1. Be related to the Report topic
2. Help satisfy the requirements specified in the report organization

Make the queries specific enough to find high-quality, relevant sources while covering the breadth needed for the report structure.
</Task>

<Format>
Call the Queries tool 
</Format>
"""

###############################################################################################################################################################################

report_planner_instructions = """I want a plan for a report that is concise and focused.

<Report topic>
The topic of the report is:
{topic}
</Report topic>

<Report organization>
The report should be organized as follows:
{report_organization}
</Report organization>

<Context>
Here is the context to use to plan the sections of the report: 
{context}
</Context>

<Task>
Generate a list of sections for the report. Your plan should be tight and focused with no overlapping sections or unnecessary filter.

For example, a good report structure might look like:
1/ intro
2/ overview of topic A
3/ overview of topic B
4/ comparison between topic A and topic B
5/ conclusion

Each of the sections should have the fields:
- Name - Name for this section of the report
- Description - A brief overview of the main topics covered in the section
- Research - Weather to perform web research for this section of the report
- Content - The content of the section which you will leave blank for now

Integration Guidelines:
- Include examples and implementation details within main topic sections, not as separate sections
- Ensure each section has a distinct purpose with no content overlap
"""