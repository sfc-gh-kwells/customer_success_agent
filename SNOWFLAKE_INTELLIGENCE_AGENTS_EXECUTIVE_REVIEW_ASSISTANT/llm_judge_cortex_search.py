"""
LLM-as-Judge Evaluation for Cortex Search Results

This script evaluates the quality and relevance of case studies retrieved by Cortex Search.

Evaluation Criteria:
1. Relevance (1-5): How well do the case studies match the user's query?
2. Completeness (1-5): Does the response cover the key aspects requested?
3. Actionability (1-5): Are the insights practical and applicable?
4. Evidence Quality (1-5): Are case studies specific with concrete details?
5. Synthesis (1-5): How well are multiple case studies combined?

Usage:
    python llm_judge_cortex_search.py <response_file> <question> <output_file>
"""

import json
import sys
import os
import snowflake.connector
from typing import Dict, Any

JUDGE_PROMPT = """You are an expert evaluator assessing the quality of case study search results from a Cortex Agent.

**User Question:** {question}

**Agent Response:** {agent_response}

**Case Studies Retrieved (from tool results):** {case_studies}

Evaluate the agent's response on these 5 dimensions (score 1-5 for each):

1. **Relevance** (1-5): How well do the retrieved case studies match the user's query?
   - 5: Perfectly relevant, directly addresses query
   - 4: Highly relevant with minor tangents
   - 3: Somewhat relevant but missing key aspects
   - 2: Partially relevant, significant gaps
   - 1: Largely irrelevant

2. **Completeness** (1-5): Does the response cover all important aspects of the query?
   - 5: Comprehensive, covers all aspects
   - 4: Covers most aspects, minor omissions
   - 3: Covers some aspects, notable gaps
   - 2: Minimal coverage
   - 1: Severely incomplete

3. **Actionability** (1-5): Are the insights practical and applicable?
   - 5: Highly actionable with clear next steps
   - 4: Actionable with good practical value
   - 3: Moderately actionable
   - 2: Limited actionability
   - 1: Not actionable

4. **Evidence Quality** (1-5): Are case studies specific with concrete details?
   - 5: Rich details, specific metrics, clear outcomes
   - 4: Good details with some specifics
   - 3: Moderate detail level
   - 2: Vague or generic
   - 1: No concrete details

5. **Synthesis** (1-5): How well are multiple case studies combined into coherent insights?
   - 5: Excellent synthesis, clear patterns identified
   - 4: Good synthesis with coherent themes
   - 3: Basic synthesis, some connections made
   - 2: Minimal synthesis, mostly listing
   - 1: No synthesis, just raw data

For each dimension:
- Provide a score (1-5)
- Provide a brief justification (1-2 sentences)

Also provide:
- **Overall Score** (average of 5 dimensions)
- **Key Strengths** (2-3 bullet points)
- **Areas for Improvement** (2-3 bullet points)

Return your evaluation in JSON format:
{{
  "relevance": {{"score": X, "justification": "..."}},
  "completeness": {{"score": X, "justification": "..."}},
  "actionability": {{"score": X, "justification": "..."}},
  "evidence_quality": {{"score": X, "justification": "..."}},
  "synthesis": {{"score": X, "justification": "..."}},
  "overall_score": X.X,
  "key_strengths": ["...", "...", "..."],
  "areas_for_improvement": ["...", "...", "..."]
}}
"""


def extract_case_studies_from_response(response_data: Dict[str, Any]) -> str:
    """Extract case study search results from response JSON."""
    case_studies = []
    
    for item in response_data.get("content", []):
        if item.get("type") == "tool_result":
            tool_result = item.get("tool_result", {})
            if "cortex_search" in str(tool_result.get("name", "")):
                content = tool_result.get("content", [])
                for c in content:
                    if "json" in c and "search_results" in c["json"]:
                        for result in c["json"]["search_results"]:
                            case_studies.append(result.get("text", ""))
    
    return "\n\n---\n\n".join(case_studies) if case_studies else "No case studies found in tool results"


def extract_agent_response(response_data: Dict[str, Any]) -> str:
    """Extract the final agent response text."""
    for item in reversed(response_data.get("content", [])):
        if item.get("type") == "text":
            return item.get("text", "")
    return "No agent response found"


def call_llm_judge(question: str, agent_response: str, case_studies: str, connection_name: str) -> Dict[str, Any]:
    """Call Snowflake Cortex LLM to judge the response."""
    
    prompt = JUDGE_PROMPT.format(
        question=question,
        agent_response=agent_response,
        case_studies=case_studies
    )
    
    conn = snowflake.connector.connect(connection_name=connection_name)
    cursor = conn.cursor()
    
    # Use Cortex Complete for judgment
    sql = """
    SELECT SNOWFLAKE.CORTEX.COMPLETE(
        'claude-3-5-sonnet',
        %(prompt)s
    ) AS judgment
    """
    
    cursor.execute(sql, {"prompt": prompt})
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    # Parse JSON response
    judgment_text = result[0]
    
    # Try to extract JSON from the response
    try:
        # Look for JSON block in markdown
        if "```json" in judgment_text:
            json_start = judgment_text.index("```json") + 7
            json_end = judgment_text.index("```", json_start)
            judgment_text = judgment_text[json_start:json_end]
        elif "```" in judgment_text:
            json_start = judgment_text.index("```") + 3
            json_end = judgment_text.index("```", json_start)
            judgment_text = judgment_text[json_start:json_end]
        
        return json.loads(judgment_text.strip())
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Warning: Could not parse JSON from LLM response: {e}")
        print(f"Raw response: {judgment_text}")
        return {"error": "Failed to parse JSON", "raw_response": judgment_text}


def main():
    if len(sys.argv) < 4:
        print("Usage: python llm_judge_cortex_search.py <response_file> <question> <output_file> [connection_name]")
        sys.exit(1)
    
    response_file = sys.argv[1]
    question = sys.argv[2]
    output_file = sys.argv[3]
    connection_name = sys.argv[4] if len(sys.argv) > 4 else os.getenv("SNOWFLAKE_CONNECTION_NAME", "MY_DEMO")
    
    # Load response data
    with open(response_file, 'r') as f:
        response_data = json.load(f)
    
    # Extract components
    agent_response = extract_agent_response(response_data)
    case_studies = extract_case_studies_from_response(response_data)
    
    print(f"Evaluating response to: {question}")
    print(f"Found {len(case_studies.split('---'))} case studies")
    print("Calling LLM judge...")
    
    # Call judge
    judgment = call_llm_judge(question, agent_response, case_studies, connection_name)
    
    # Save results
    output_data = {
        "question": question,
        "response_file": response_file,
        "judgment": judgment,
        "metadata": {
            "agent_response_length": len(agent_response),
            "num_case_studies": len(case_studies.split('---'))
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✅ Judgment saved to: {output_file}")
    print(f"\nOverall Score: {judgment.get('overall_score', 'N/A')}/5.0")
    
    if "overall_score" in judgment:
        print("\nScores:")
        for dimension in ["relevance", "completeness", "actionability", "evidence_quality", "synthesis"]:
            if dimension in judgment:
                score = judgment[dimension].get("score", "N/A")
                print(f"  {dimension.title()}: {score}/5")


if __name__ == "__main__":
    main()
