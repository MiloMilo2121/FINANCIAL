"""Structured prompt templates for Perplexity Sonar API.

Prompt engineering principles applied:
  1. Clear scope limitation: "Focus exclusively on X"
  2. Multi-perspective mandate: Bullish AND bearish factors
  3. Source citation requirement: "Cite primary sources"
  4. Fact-checking instruction: "Cross-reference with authoritative data"
  5. JSON output mandate: "Return ONLY valid JSON matching this schema"
  6. Anti-hallucination guardrails: "If uncertain, set confidence < 0.5"

The system prompt establishes the LLM's role as an institutional analyst.
The user prompt provides current context and the JSON schema to follow.
"""

from datetime import datetime, timezone


SYSTEM_PROMPT = """You are a senior quantitative analyst at a top-tier commodity trading firm,
specializing in precious metals markets with 20 years of experience in gold (XAU/USD) analysis.

Your analysis integrates:
- Technical analysis (price action, volume, momentum indicators)
- Fundamental analysis (supply/demand, central bank reserves, mine production)
- Macroeconomic analysis (real interest rates, DXY correlation, inflation expectations)
- Geopolitical risk assessment (safe-haven demand, conflict escalation)
- Institutional positioning (COT data, ETF flows, COMEX warehouse stocks)

CRITICAL INSTRUCTIONS:
1. Be objective and present BOTH bullish and bearish factors
2. Always cite primary sources (central bank publications, COMEX reports, SEC filings)
3. Do NOT speculate beyond available data — set confidence < 0.5 when uncertain
4. Return ONLY valid JSON — no markdown, no preamble, no explanation outside the JSON
5. Your JSON must conform exactly to the provided schema
"""


def build_gold_sentiment_prompt(
    asset: str = "XAU",
    context: str = "",
    time_horizon: str = "medium",
    current_price: float | None = None,
) -> str:
    """Build a structured sentiment analysis prompt for gold.

    Args:
        asset: Asset symbol (default "XAU").
        context: Additional context (recent news, macro data).
        time_horizon: Analysis horizon ('short', 'medium', 'long').
        current_price: Current spot price for context.

    Returns:
        Complete user prompt string for the Sonar API.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    price_context = f"Current {asset}/USD spot: ${current_price:.2f}" if current_price else ""

    return f"""Analyze {asset}/USD sentiment as of {now}.
{price_context}
{context}

Analyze these four dimensions:
1. MEDIA SENTIMENT: Financial media (FT, WSJ, Bloomberg) tone over the past 6 months
2. INSTITUTIONAL BEHAVIOR: Changes in institutional ownership, options market positioning
3. MARKET POSITIONING: Put/call ratios, ETF flows (GLD, IAU), COMEX net long position changes
4. GEOPOLITICAL FACTORS: Current conflict risks, central bank reserve accumulation/selling

Time horizon for your analysis: {time_horizon}-term

Perform fact-checking by cross-referencing:
- WGC (World Gold Council) data
- CME COMEX official inventory reports
- IMF/BIS central bank reserve publications
- SEC 13F filings for institutional ownership

Return your complete analysis as JSON matching EXACTLY this schema:
{{
    "asset_sentiment": {{
        "asset": "{asset}",
        "sentiment_score": <float -1.0 to 1.0>,
        "direction": <"bullish"|"bearish"|"neutral">,
        "confidence": <float 0.0 to 1.0>,
        "key_drivers": [<string>, ...],
        "time_horizon": <"short"|"medium"|"long">
    }},
    "geopolitical_risk": {{
        "threat_level": <integer 0-4>,
        "primary_risk_factors": [<string>, ...],
        "affected_regions": [<string>, ...],
        "gold_impact_direction": <"bullish"|"bearish"|"neutral">,
        "gold_impact_magnitude": <float 0.0 to 1.0>
    }},
    "market_positioning": {{
        "put_call_ratio": <float or null>,
        "institutional_flow_direction": <"bullish"|"bearish"|"neutral"|null>,
        "etf_flow_usd_billions": <float or null>,
        "comex_net_long_change": <float or null>
    }},
    "macro_context": "<2-3 sentence macro context>",
    "citations": ["<source URL or publication>", ...],
    "fact_check_confidence": <float 0.0 to 1.0>,
    "analysis_timestamp": "{now}"
}}"""


def build_news_fact_check_prompt(headline: str, body: str | None = None) -> str:
    """Build a prompt for fact-checking a specific news item."""
    content = body or headline
    return f"""Fact-check the following financial news item about precious metals:

HEADLINE: {headline}
CONTENT: {content[:2000] if content else '(no body)'}

1. Search for corroborating evidence from primary sources (SEC, COMEX, central banks)
2. Identify if this is verified fact, speculation, or likely misinformation
3. Rate the reliability on a scale of 0.0 (unreliable) to 1.0 (fully verified)
4. Identify the key entities mentioned and their actual market positions

Return JSON:
{{
    "is_factual": <boolean>,
    "reliability_score": <float 0.0 to 1.0>,
    "corroborating_sources": [<source>, ...],
    "contradicting_sources": [<source>, ...],
    "key_entities": [<entity name>, ...],
    "market_impact_direction": <"bullish"|"bearish"|"neutral"|"unknown">,
    "fact_check_summary": "<2 sentence summary>"
}}"""
