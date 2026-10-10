from core.provider_http import QueryError, cli_path, output, run_cli


def query():
    exe = cli_path("kiro-cli")
    run_cli([exe, "whoami", "--format", "json"], timeout=4)
    text = run_cli([exe, "chat", "--no-interactive", "/usage"], timeout=12)
    if not text.strip():
        raise QueryError("Kiro returned no usage; check CLI compatibility and sign-in.")
    return text


def main():
    output(query)


if __name__ == "__main__":
    main()
