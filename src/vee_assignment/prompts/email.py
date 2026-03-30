EMAIL_REQUIREMENTS_PROMPT = """Determine whether this email request has enough information to proceed.

Allowed categories:
- Donation Thank You Email
- Inform about Volunteering Opportunities
- Ask Availability for a Meeting

Goal:
- Identify whether the request maps to one supported category.
- Determine if there are enough details to draft now (balanced strictness).

Policy:
- If user gives at least one concrete instruction/detail, enough_info=true.
- Category alone is not enough detail. For example, "draft a donor thank-you email" should set enough_info=false and ask what to include.
- If user request is generic (for example, "help me draft an email"), enough_info=false and ask a concise follow-up.
- If category is unsupported, set category_supported=false and enough_info=false.
- If category is missing but could be clarified, set category_supported=true and enough_info=false.

User request:
{user_request}
"""


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
- Explicitly incorporate user-provided details from the request when present.
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
