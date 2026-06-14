import google.generativeai as genai
import json
import os
import re


def analyze_policy(text):
    """
    Send extracted PDF text to Gemini API and return structured policy data.
    Returns a dict with keys: policy_name, description, benefits, eligibility, last_date.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    print("DEBUG API KEY =", api_key)
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment variables.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""You are a policy document analyzer. Your job is to extract specific structured information from the provided policy document text.

Extract the following information from the policy document:
1. Policy Name
2. Description (a clear summary of what the policy is about)
3. Benefits (list all key benefits provided)
4. Eligibility Criteria (list all eligibility conditions)
5. Last Date to Apply

STRICT RULES:
- Use ONLY information that is explicitly present in the document.
- Do NOT assume, infer, or generate any information not found in the text.
- If any field is missing or not mentioned in the document, return exactly the string "Not Specified".
- Benefits and Eligibility must be returned as arrays of strings (even if only one item).
- Return ONLY a valid JSON object. No explanation, no markdown, no backticks.

Return this exact JSON structure:
{{
  "policy_name": "string or Not Specified",
  "description": "string or Not Specified",
  "benefits": ["benefit 1", "benefit 2"] or ["Not Specified"],
  "eligibility": ["criteria 1", "criteria 2"] or ["Not Specified"],
  "last_date": "string or Not Specified"
}}

Policy Document Text:
\"\"\"
{text}
\"\"\"

Return only the JSON object:"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

        data = json.loads(raw)

        # Normalize and validate fields
        result = {
            "policy_name": _clean_str(data.get("policy_name")),
            "description": _clean_str(data.get("description")),
            "benefits": _clean_list(data.get("benefits")),
            "eligibility": _clean_list(data.get("eligibility")),
            "last_date": _clean_str(data.get("last_date")),
        }
        return result

    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {str(e)}\nRaw response: {raw[:500]}")
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {str(e)}")


def _clean_str(value):
    if not value or str(value).strip() == "":
        return "Not Specified"
    val = str(value).strip()
    if val.lower() in ["not specified", "n/a", "none", "null", "-", "–"]:
        return "Not Specified"
    return val


def _clean_list(value):
    if not value:
        return ["Not Specified"]
    if isinstance(value, list):
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        if not cleaned:
            return ["Not Specified"]
        # If only one item and it says "not specified"
        if len(cleaned) == 1 and cleaned[0].lower() in ["not specified", "n/a", "none", "null"]:
            return ["Not Specified"]
        return cleaned
    # If it's a string
    val = str(value).strip()
    if val.lower() in ["not specified", "n/a", "none", "null", ""]:
        return ["Not Specified"]
    return [val]
