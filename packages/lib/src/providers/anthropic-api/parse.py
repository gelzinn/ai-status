from core.metered import cost_metrics


def parse(raw_output):
    return cost_metrics(raw_output, "Anthropic API", cents=True)
