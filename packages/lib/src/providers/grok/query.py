from core.extra_providers import collect
from core.provider_http import output


def query():
    return collect('grok')


def main():
    output(query)


if __name__ == "__main__":
    main()
