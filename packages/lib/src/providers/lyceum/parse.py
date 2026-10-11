from core.extra_providers import parse as parse_provider


def parse(raw):
    return parse_provider('lyceum', raw)
