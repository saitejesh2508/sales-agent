"""Opt-in Hindsight smoke check using synthetic lead data."""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true", help="Make live Hindsight API calls."
    )
    args = parser.parse_args()
    if not args.run:
        print("Skeleton only. Pass --run to call Hindsight after configuring keys.")
        return

    from dotenv import load_dotenv

    load_dotenv()
    required = ("HINDSIGHT_API_URL", "HINDSIGHT_API_KEY")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        parser.error("Missing configuration: " + ", ".join(missing))

    from hindsight_client import Hindsight

    client = Hindsight(
        base_url=os.environ["HINDSIGHT_API_URL"],
        api_key=os.environ["HINDSIGHT_API_KEY"],
    )
    bank_id = "sales-agent-demo"
    client.retain(
        bank_id=bank_id,
        content=(
            "Synthetic demo lead Alex prefers Spanish, is evaluating a sales "
            "assistant, and asked for a follow-up next Tuesday."
        ),
    )
    print("Retain completed.")
    recalled = client.recall(
        bank_id=bank_id, query="What language does demo lead Alex prefer?"
    )
    print("Recall:", recalled)
    reflected = client.reflect(
        bank_id=bank_id,
        query="How should the rep follow up with demo lead Alex?",
    )
    print("Reflect:", reflected)


if __name__ == "__main__":
    main()
