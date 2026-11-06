"""Explicitly seed the four requested lead histories; never run on page load."""

from agent import EMPTY_BANK_ID, memory
from leads import LEADS

HISTORIES = {
    "lead-alex-rivera": (
        "Alex Rivera is the operations lead at Clínica Norte and prefers Spanish. "
        "The finance director must attend. The meeting is confirmed for "
        "10 November 2026 at 16:30. This confirmed status supersedes the earlier requested status. "
        "Alex is evaluating a sales assistant. Timezone has not been specified."
    ),
    "lead-mei-chen": (
        "Mei Chen is at Northwind Clinic. There has been one past call in Mandarin. "
        "Mei objected to the annual price. There is no meeting yet. "
        "No price amount, budget, role, decision maker, or explicit language preference has been provided."
    ),
    "lead-luis-ortega": (
        "The only known details are the lead name Luis Ortega and company Taller Sol. "
        "There has been no conversation yet. Language preference, role, needs, budget, "
        "decision makers, and meeting details are unknown."
    ),
    "lead-hana-okonkwo": (
        "Hana Okonkwo is at BrightPath. Hana prefers English and email. "
        "Hana went quiet after a generic follow-up. The reason for not replying, role, "
        "business needs, budget, and meeting details have not been provided."
    ),
}


def main():
    with memory() as client:
        client.create_bank(bank_id=EMPTY_BANK_ID, name="Empty comparison")
        for lead in LEADS:
            client.create_bank(bank_id=lead["id"], name=lead["name"])
            client.retain(bank_id=lead["id"], document_id=f"{lead['id']}-sales-desk-history",
                          content=HISTORIES[lead["id"]], context="Lead history supplied by the rep.")
            print(f"Seeded {lead['name']}.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Lead seeding failed. Check service availability and local configuration.")
