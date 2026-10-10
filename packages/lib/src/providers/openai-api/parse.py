from core.metered import cost_metrics


def parse(raw_output):
    return cost_metrics(raw_output, "OpenAI API")
