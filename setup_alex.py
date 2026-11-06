"""Explicit one-time bank setup using the history supplied by the user."""

from agent import BANK_ID, EMPTY_BANK_ID, memory


def main():
    with memory() as client:
        client.create_bank(bank_id=BANK_ID, name="Alex Rivera")
        client.create_bank(bank_id=EMPTY_BANK_ID, name="Empty comparison")
        client.retain(
            bank_id=BANK_ID,
            document_id="alex-rivera-history",
            content=("Alex Rivera is the operations lead at Clínica Norte. Alex prefers Spanish "
                     "and is evaluating a sales assistant. Alex requested a follow-up for "
                     "10 November 2026 at 16:30 with the finance director. "
                     "This is a requested meeting; confirmation and timezone have not yet been provided."),
            context="Lead history provided by the rep.",
        )
    print("Alex Rivera history retained. Comparison bank created with no retained facts.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Bank setup failed. Check local configuration and service availability.")
