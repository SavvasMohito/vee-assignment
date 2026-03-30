SEARCH_PLAN_PROMPT = """Create one focused web search query for this post request.

Organization name: {organization_name}
Organization website: {organization_url}
Target platform: {platform}
User request: {user_request}

Return a query likely to surface relevant, recent context.
"""


RESEARCH_SUMMARY_PROMPT = """Synthesize the raw web research into concise bullet points.
Keep only high-confidence facts and themes.

Raw research:
{research_blob}
"""


PILLAR_PROMPT = """Choose the best nonprofit content pillar for this request.

Pillars:
- Impact & Mission
- Education & Awareness
- Community & Events
- Fundraising & Donations
- People & Culture

Organization name: {organization_name}
Platform: {platform}
User request: {user_request}
Research summary:
{research_summary}
"""


DRAFT_PROMPT = """Draft one social media post.

Organization:
- Name: {organization_name}
- URL: {organization_url}

Target platform: {platform}
Selected pillar: {pillar}
User request: {user_request}
Research summary:
{research_summary}

Return:
- post text
- up to 6 hashtags relevant to the platform
- short rationale of tone/format choices
"""


REVIEW_PROMPT = """Review this drafted social post for factual safety and quality.
If needed, rewrite it to be safer and clearer while preserving intent.

Draft:
{post_text}

Research summary:
{research_summary}
"""
