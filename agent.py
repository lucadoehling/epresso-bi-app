"""Assistant: a dispatcher plus a router.
The router (rules now, a language model later) only CHOOSES a tool and its
arguments. Our code RUNS the tool. Nothing here executes model-written code."""
from __future__ import annotations

import analytics
from analytics import ToolResult

# The ONLY things the assistant may do. The E-Presso tools use the same metric
# definitions as the validated dashboard and receive its current filtered rows.
TOOLS = {
    'get_revenue_by_channel': {
        'fn': analytics.get_revenue_by_channel,
        'params': set(),
        'description': 'Calculate revenue by Website versus Brick & Mortar.',
    },
    'get_annual_revenue_trend': {
        'fn': analytics.get_annual_revenue_trend,
        'params': set(),
        'description': 'Calculate revenue by calendar year.',
    },
    'get_monthly_revenue_share': {
        'fn': analytics.get_monthly_revenue_share,
        'params': set(),
        'description': 'Calculate monthly revenue and share of current-scope revenue.',
    },
    'get_category_performance': {
        'fn': analytics.get_category_performance,
        'params': set(),
        'description': 'Calculate revenue by product category.',
    },
    'explain_limitation': {
        'fn': analytics.explain_limitation,
        'params': {'topic'},
        'description': 'Check whether current data supports profitability or causal claims.',
    },
    'unsupported_request': {
        'fn': analytics.unsupported_request,
        'params': set(),
        'description': 'Log that a request did not match an approved calculation.',
    },
    'get_total': {
        'fn': analytics.get_total,
        'params': {'value_col', 'filters'},
        'description': 'Sum a numeric column, optionally filtered.',
    },
    'group_total': {
        'fn': analytics.group_total,
        'params': {'value_col', 'group_col', 'filters'},
        'description': 'Sum a numeric column by group (store, channel, year, ...).',
    },
    'data_quality_report': {
        'fn': analytics.data_quality_report,
        'params': set(),
        'description': 'Report duplicates and missing values in the loaded data.',
    },
}

UNSUPPORTED = ('I can only answer questions that my approved analytical functions can '
               'calculate from the loaded data: ' + ', '.join(TOOLS) + '. '
               'I cannot answer that one.')

# For when you add a language model: keep these rules in the system prompt.
SYSTEM_PROMPT = """You are an analytical assistant for E-Presso managers.
Rules:
- Only state numbers that appear in a tool result. Never estimate or recall figures.
- Always call a tool before making a numerical claim.
- State the scope (which filters/period) of every answer.
- Separate Findings (from tool results), Interpretation, and Next steps.
- Revenue is not profit. Association is not causation.
- If the data cannot support a conclusion, say so and name the missing information.
- Never ask for, run, or write code. Never modify data."""


def run_tool(name: str, args: dict, df, log: list) -> ToolResult:
    """The dispatcher: validate the request, run the function, log the call."""
    if name not in TOOLS:
        result = analytics._error(name, f'Unknown tool: {name}')
    else:
        unexpected = set(args) - TOOLS[name]['params']
        if unexpected:
            result = analytics._error(name, f'Unexpected argument(s): {sorted(unexpected)}')
        else:
            result = TOOLS[name]['fn'](df, **args)
    log.append({'tool': name, 'arguments': args, 'result': result.to_dict()})
    return result


def rules_router(question: str, df):
    """Route supported question patterns to an allowlisted analytical tool."""
    q = question.lower()
    if any(phrase in q for phrase in ('profit', 'margin', 'cost')):
        return 'explain_limitation', {'topic': 'profitability'}
    if any(phrase in q for phrase in ('cause', 'causal', 'causation')):
        return 'explain_limitation', {'topic': 'causation'}
    if any(w in q for w in ('missing', 'duplicate', 'quality', 'blank')):
        return 'data_quality_report', {}
    if any(phrase in q for phrase in ('channel', 'store type', 'website', 'brick')):
        return 'get_revenue_by_channel', {}
    if any(phrase in q for phrase in ('annual', 'by year', 'yearly', 'trend')):
        return 'get_annual_revenue_trend', {}
    if any(phrase in q for phrase in ('month', 'monthly', 'season', 'share')):
        return 'get_monthly_revenue_share', {}
    if any(phrase in q for phrase in ('category', 'categories')):
        return 'get_category_performance', {}
    return None


def llm_router(question: str, df):
    """Option A router. TODO: after the rules-based version works, ask a model that
    supports function calling to choose from TOOLS. Return (name, args) or None."""
    raise NotImplementedError('Add the language-model router after your tools are tested.')


def format_findings(result: ToolResult) -> str:
    if result.error:
        return f'The request could not be completed: {result.error}'
    return f'{result.definition}: {result.value}  (rows used: {result.rows_used})'


def answer_question(question: str, df, mode: str = 'rules') -> dict:
    log: list = []
    routed = rules_router(question, df) if mode == 'rules' else llm_router(question, df)
    if routed is None:
        result = run_tool('unsupported_request', {}, df, log)
        return {'scope': 'n/a', 'findings': UNSUPPORTED, 'interpretation': '',
                'next_steps': 'Ask about one of the supported topics in the tool result.',
                'tool_log': log}
    name, args = routed
    result = run_tool(name, args, df, log)
    return {
        'scope': str(result.scope),
        'findings': format_findings(result),
        'interpretation': ' '.join(result.caveats),
        'next_steps': '',
        'tool_log': log,
    }
