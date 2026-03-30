EMAIL_CATEGORY_PROMPT = """Classify the email request into exactly one allowed category.

Allowed categories:
- Donation Thank You Email
- Inform about Volunteering Opportunities
- Ask Availability for a Meeting

If the message does not fit any allowed category:
- pick the closest category
- set fits_allowed_categories to false
- explain why it is unsupported in reasoning.

User request:
{user_request}
"""


EMAIL_DRAFT_PROMPT = """Draft an email as if you are a representative of the organization.

Organization:
- Name: {organization_name}
- URL: {organization_url}

Email category: {email_category}
User request: {user_request}

Rules:
- Keep a professional and warm nonprofit tone.
- Include a clear subject line.
- Include placeholders only when specifics are missing.
- If category is "Ask Availability for a Meeting", include meeting scope in the body.

Return:
- subject
- body
- short rationale
"""


EMAIL_REVIEW_PROMPT = """Review this drafted email for safety, clarity, and category compliance.
If needed, rewrite to improve quality while preserving intent.

Email category: {email_category}
Draft subject:
{subject}

Draft body:
{body}
"""
