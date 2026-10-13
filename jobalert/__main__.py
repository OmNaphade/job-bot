import argparse
import logging
import sys

from .config import env, load_config
from .notify import Telegram, source_label
from .pipeline import run


def _print_report(result, dry_run: bool) -> None:
    print(f"\n{'source':<28}{'fetched':>8}{'new':>6}  status")
    for report in sorted(result.reports, key=lambda r: r.name):
        status = f"FAILED: {report.error}" if report.error else f"skipped ({report.skipped})" if report.skipped else "ok"
        print(f"{report.name:<28}{report.fetched:>8}{report.new:>6}  {status}")
    if result.rejected:
        print("\nfiltered out: " + ", ".join(f"{n} {why}" for why, n in sorted(result.rejected.items())))
    verb = "would send" if dry_run else "sent"
    count = len(result.to_send) if dry_run else result.sent
    print(f"\n{verb} {count} alert(s)" + ("  [first run]" if result.first_run else ""))
    if dry_run:
        for job in result.to_send:
            print(f"  [{job.score:>2}] {job.title} | {job.company} | {job.location} | {source_label(job.source)}")
            print(f"       {job.link}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="jobalert", description="Push new matching jobs to Telegram.")
    parser.add_argument("--config", help="path to config.yaml (default: ./config.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="fetch, filter and send new jobs once")
    run_parser.add_argument("--dry-run", action="store_true", help="print what would be sent; send nothing, save nothing")
    run_parser.add_argument("--only", help="only sources whose name contains this (e.g. linkedin)")
    commands.add_parser("test-telegram", help="send a test message to check your bot token and chat id")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    config = load_config(args.config)
    if args.command == "test-telegram":
        telegram = Telegram(env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID"))
        if not telegram.configured:
            print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set (see .env.example).")
            return 1
        ok = telegram.send_text("✅ <b>Job alert</b> can reach you here.")
        print("Sent. Check Telegram." if ok else "Telegram rejected the message; see the error above.")
        return 0 if ok else 1

    result = run(config, dry_run=args.dry_run, only=args.only)
    _print_report(result, args.dry_run)
    # A broken source shouldn't fail the whole run, but if *nothing* worked, say so loudly.
    return 1 if result.reports and all(r.error for r in result.reports) else 0


if __name__ == "__main__":
    sys.exit(main())
