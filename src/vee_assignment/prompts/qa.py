QA_SCOPE_PROMPT = """Decide whether this user message should be handled as organization Q&A.

Organization context:
- Name: {organization_name}
- URL: {organization_url}

User question/message:
{user_request}

Rules:
- If the user is asking for factual information about the organization, its programs,
  team, impact, events, plans, or public activities, mark organization_related=true.
- If answer can be attempted using public website/web context, set answerable_with_public_context=true.
- If the message is unrelated to the organization (e.g., general trivia), set organization_related=false.
- If unrelated or not answerable from public org context, provide a short redirect message.
"""


QA_SEARCH_PLAN_PROMPT = """Create one focused web search query to answer the user question.

Organization:
- Name: {organization_name}
- URL: {organization_url}

Question:
{qa_question}

Return one query that prioritizes organization-relevant and recent public information.
"""


QA_ANSWER_PROMPT = """Answer the user question as accurately as possible using available context.

Organization:
- Name: {organization_name}
- URL: {organization_url}

Question:
{qa_question}

Website context:
{qa_website_context}

Web research context:
{qa_research_blob}

Instructions:
- Use only supported information from the provided context.
- If information is incomplete, be transparent and cautious.
- Keep the answer clear, concise, and helpful.
- Include up to 5 source URLs that best support the answer.
"""
