import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_report(result: dict, query: str, output_path: str | None = None) -> str:
    """
    Generate a formatted Markdown report from analysis results.

    Args:
        result: The dict returned by FinancialAnalysisSystem.analyze().
        query: The original user query.
        output_path: Optional file path to save the report. If None, returns string only.

    Returns:
        The report as a Markdown string.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []

    lines.append("# Financial Analysis Report")
    lines.append(f"\n**Generated:** {timestamp}")
    lines.append(f"\n**Query:** {query}")

    # Error case
    if "error" in result:
        lines.append(f"\n## Error\n\n{result['error']}")
        return _finalize(lines, output_path)

    # Summary
    if result.get("summary"):
        lines.append(f"\n## Summary\n\n{result['summary']}")

    # Confidence + data sources used
    if result.get("confidence"):
        lines.append(f"\n**Confidence:** {result['confidence']}")
    if result.get("data_sources_used"):
        lines.append(f"\n**Sources used:** {', '.join(result['data_sources_used'])}")
    if result.get("currency_note"):
        lines.append(f"\n**Currency note:** {result['currency_note']}")

    # Key Findings
    if result.get("key_findings"):
        lines.append("\n## Key Findings\n")
        for finding in result["key_findings"]:
            lines.append(f"- {finding}")

    # Macro Context (new synthesis field)
    if result.get("macro_context"):
        lines.append(f"\n## Macroeconomic Context\n\n{result['macro_context']}")

    # Caveats
    if result.get("caveats"):
        lines.append("\n## Caveats\n")
        for caveat in result["caveats"]:
            lines.append(f"- {caveat}")

    # --- Extracted Data ---
    extracted = result.get("extracted_data", {})
    if extracted and "raw_response" not in extracted:
        # New schema: {company_data: [...], macro_data: [...], notes: "..."}
        company_data = extracted.get("company_data", [])
        macro_data = extracted.get("macro_data", [])

        # Fallback: old flat schema (company, period, metrics at top level)
        if not company_data and extracted.get("company"):
            company_data = [extracted]

        if company_data:
            lines.append("\n## Extracted Company Data\n")
            for co in company_data:
                company_name = co.get("company") or co.get("ticker") or "Unknown"
                period = co.get("period", "")
                currency = co.get("currency", "")
                header_parts = [company_name]
                if period:
                    header_parts.append(period)
                if currency:
                    header_parts.append(f"({currency})")
                lines.append(f"\n### {' — '.join(header_parts)}\n")

                metrics = co.get("metrics", {})
                if metrics:
                    lines.append("| Metric | Value | Unit |")
                    lines.append("|--------|-------|------|")
                    for name, detail in metrics.items():
                        if isinstance(detail, dict):
                            val = detail.get("value", "N/A")
                            unit = detail.get("unit", "")
                            lines.append(f"| {name} | {val} | {unit} |")

                raw_figures = co.get("raw_figures", [])
                if raw_figures:
                    lines.append("\n**Raw figures:**")
                    for fig in raw_figures:
                        source = fig.get("source", "")
                        src_str = f" *(source: {source})*" if source else ""
                        lines.append(
                            f"- {fig.get('label', '')}: {fig.get('value', '')} "
                            f"{fig.get('unit', '')}{src_str}"
                        )

        if macro_data:
            lines.append("\n## Extracted Macro Data\n")
            lines.append("| Indicator | Source | Geography | Latest Value | Trend |")
            lines.append("|-----------|--------|-----------|--------------|-------|")
            for m in macro_data:
                lines.append(
                    f"| {m.get('indicator', '')} | {m.get('source', '')} "
                    f"| {m.get('geography', '')} | {m.get('latest_value', 'N/A')} "
                    f"{m.get('unit', '')} | {m.get('trend_note', '')} |"
                )

        if extracted.get("notes"):
            lines.append(f"\n*{extracted['notes']}*")

    # --- Trends ---
    trends = result.get("trends", {})
    if trends and "raw_response" not in trends:
        # New schema: {company_trends: [...], macro_trends: [...], outlook: {short_term, medium_term, key_risks}}
        company_trends = trends.get("company_trends", [])
        macro_trends = trends.get("macro_trends", [])

        # Fallback: old flat schema (trends list at top level)
        if not company_trends and trends.get("trends"):
            company_trends = [{"company": "", "trends": trends["trends"], "anomalies": trends.get("anomalies", [])}]

        if company_trends:
            lines.append("\n## Trends\n")
            for co in company_trends:
                company_name = co.get("company") or co.get("ticker") or ""
                if company_name:
                    lines.append(f"\n### {company_name}\n")

                trend_list = co.get("trends", [])
                if trend_list:
                    lines.append("| Metric | Direction | Strength | Change Rate | Horizon | Period |")
                    lines.append("|--------|-----------|----------|-------------|---------|--------|")
                    for t in trend_list:
                        lines.append(
                            f"| {t.get('metric', '')} | {t.get('direction', '')} "
                            f"| {t.get('direction_strength', '')} "
                            f"| {t.get('change_rate', '') or t.get('magnitude', '')} "
                            f"| {t.get('time_horizon', '')} | {t.get('period', '')} |"
                        )

                anomalies = co.get("anomalies", [])
                if anomalies:
                    lines.append("\n**Anomalies:**")
                    for a in anomalies:
                        lines.append(f"- **{a.get('severity', '')}:** {a.get('description', '')}")

        if macro_trends:
            lines.append("\n### Macro Trends\n")
            lines.append("| Indicator | Direction | Change Rate | Relevance |")
            lines.append("|-----------|-----------|-------------|-----------|")
            for m in macro_trends:
                lines.append(
                    f"| {m.get('indicator', '')} | {m.get('direction', '')} "
                    f"| {m.get('change_rate', '')} | {m.get('relevance_to_companies', '')} |"
                )

        if trends.get("cross_company_comparison") and trends["cross_company_comparison"] != "null":
            lines.append(f"\n**Cross-company comparison:** {trends['cross_company_comparison']}")

        outlook = trends.get("outlook", {})
        if isinstance(outlook, dict):
            if outlook.get("short_term"):
                lines.append(f"\n**Near-term outlook:** {outlook['short_term']}")
            if outlook.get("medium_term"):
                lines.append(f"\n**Medium-term outlook:** {outlook['medium_term']}")
            if outlook.get("key_risks"):
                lines.append("\n**Key risks:**")
                for r in outlook["key_risks"]:
                    lines.append(f"- {r}")
        elif isinstance(outlook, str) and outlook:
            # Fallback: old schema had outlook as string
            lines.append(f"\n**Outlook:** {outlook}")

    # --- Sentiment ---
    sentiment = result.get("sentiment", {})
    if sentiment and "raw_response" not in sentiment:
        lines.append("\n## Sentiment Analysis\n")
        overall = sentiment.get("overall_sentiment", "N/A")
        horizon = sentiment.get("time_horizon", "")
        horizon_str = f" ({horizon}-term)" if horizon else ""
        lines.append(f"**Overall:** {overall}{horizon_str}")

        # Per-company sentiment
        for co_sent in sentiment.get("company_sentiment", []):
            company_name = co_sent.get("company", "")
            co_sentiment = co_sent.get("sentiment", "")
            co_summary = co_sent.get("summary", "")
            if company_name:
                lines.append(f"\n**{company_name}:** {co_sentiment} — {co_summary}")

        # Macro sentiment
        macro_sent = sentiment.get("macro_sentiment", {})
        if isinstance(macro_sent, dict) and macro_sent.get("summary"):
            lines.append(f"\n**Macro sentiment:** {macro_sent.get('sentiment', '')} — {macro_sent['summary']}")

        # Positive signals — new schema: list of dicts; old schema: list of strings
        pos = sentiment.get("positive_signals", [])
        if pos:
            lines.append("\n**Positive signals:**")
            for s in pos:
                if isinstance(s, dict):
                    credibility = s.get("credibility", "")
                    src = s.get("source_type", "")
                    cred_str = f" *[{src}, {credibility}]*" if (src or credibility) else ""
                    lines.append(f"- {s.get('signal', s)}{cred_str}")
                else:
                    lines.append(f"- {s}")

        # Negative signals
        neg = sentiment.get("negative_signals", [])
        if neg:
            lines.append("\n**Negative signals:**")
            for s in neg:
                if isinstance(s, dict):
                    credibility = s.get("credibility", "")
                    src = s.get("source_type", "")
                    cred_str = f" *[{src}, {credibility}]*" if (src or credibility) else ""
                    lines.append(f"- {s.get('signal', s)}{cred_str}")
                else:
                    lines.append(f"- {s}")

        # Risk factors
        risks = sentiment.get("risk_factors", [])
        if risks:
            lines.append("\n**Risk factors:**")
            for r in risks:
                lines.append(f"- {r}")

        # Forward guidance — new schema: dict; old schema: string
        fg = sentiment.get("forward_guidance", {})
        if isinstance(fg, dict):
            if fg.get("management"):
                lines.append(f"\n**Management guidance:** {fg['management']}")
            if fg.get("analyst_signals"):
                lines.append(f"\n**Analyst signals:** {fg['analyst_signals']}")
            if fg.get("macro_outlook"):
                lines.append(f"\n**Macro outlook:** {fg['macro_outlook']}")
        elif isinstance(fg, str) and fg:
            lines.append(f"\n**Forward guidance:** {fg}")

        if sentiment.get("geographic_note") and sentiment["geographic_note"] != "null":
            lines.append(f"\n*Geographic note: {sentiment['geographic_note']}*")

    # --- Validation ---
    validation = result.get("validation", {})
    if validation and "raw_response" not in validation:
        lines.append("\n## Validation\n")

        consistent = validation.get("is_consistent")
        if consistent is not None:
            status = "Consistent" if consistent else "Inconsistencies found"
            lines.append(f"**Status:** {status}")

        if validation.get("highest_severity_issue"):
            lines.append(f"\n**Highest severity issue:** {validation['highest_severity_issue']}")

        dq = validation.get("data_quality")
        dq_reason = validation.get("data_quality_reason", "")
        if dq:
            lines.append(f"\n**Data quality:** {dq}" + (f" — {dq_reason}" if dq_reason else ""))

        issues = validation.get("issues", [])
        if issues:
            lines.append("\n**Issues:**")
            for issue in issues:
                lines.append(
                    f"- [{issue.get('severity', '')}] {issue.get('description', '')}"
                )

        verified = validation.get("verified_claims", [])
        if verified:
            lines.append("\n**Verified claims:**")
            for claim in verified:
                lines.append(f"- {claim}")

        if validation.get("recommendation"):
            lines.append(f"\n**Recommendation:** {validation['recommendation']}")

    lines.append("\n---\n*Generated by Multi-Agent Financial Analysis System*")

    return _finalize(lines, output_path)


def _finalize(lines: list[str], output_path: str | None) -> str:
    """Join lines and optionally write to file."""
    report = "\n".join(lines)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        logger.info(f"Report saved to {output_path}")

    return report
