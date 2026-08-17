"""Seed sample transcripts into whatever database DATABASE_URL points at.

Usage:
    DATABASE_URL="postgresql://..." python scripts/seed_transcripts.py [count]

Standalone - talks to the DB directly via SQLAlchemy, independent of the
app's config.py/.env loading, so it can target any database (e.g. Neon)
just by setting DATABASE_URL for this one process.
"""
import os
import random
import sys
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from apis.models.transcript.model import Transcript  # noqa: E402

DOMAINS = [
    "Pharma Data", "Legal Ops", "EdTech Platforms", "Manufacturing Automation",
    "Supply Chain Logistics", "Construction Procurement", "Fintech Payments",
    "Healthcare Interoperability", "Retail Customer Experience", "Cloud Cost Optimization",
    "Telecom Infrastructure", "Insurance Underwriting", "Enterprise SaaS",
    "Gaming Compliance", "Cybersecurity Operations",
]
GEOGRAPHIES = [
    "North America", "Europe", "Asia Pacific", "South Asia",
    "Middle East & Africa", "Latin America",
]
DESIGNATIONS = [
    "VP of Sales", "Senior Director", "Chief Technology Officer", "Head of Product",
    "VP of Customer Success", "VP of Operations", "VP of Revenue Operations",
    "Director of Engineering",
]
FIRST_NAMES = ["Daniel", "Priya", "James", "Aisha", "Sarah", "Wei", "Emma", "Sofia", "Fatima"]
LAST_NAMES = ["Mitchell", "Singh", "Chen", "Patel", "Garcia", "Verma", "Novak", "Hassan", "Okafor"]


def build_transcript(seed_id: int) -> Transcript:
    domain = random.sample(DOMAINS, k=random.randint(1, 3))
    geography = random.sample(GEOGRAPHIES, k=random.randint(1, 4))
    topic = f"{domain[0]} trends heading into 2026 (seed-{seed_id})"
    published_at = datetime.utcnow() - timedelta(days=random.randint(0, 30))
    slug = domain[0].lower().replace(" ", "-")

    return Transcript(
        fk_expert=random.randint(1, 50),
        expert_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
        designation=random.choice(DESIGNATIONS),
        years_of_experience=random.randint(3, 20),
        topic=topic,
        domains=domain,
        geographies=geography,
        preview=(
            f"This conversation covers the practical realities of {domain[0]} today, "
            "including where budgets are actually going and what is getting cut."
        ),
        final_transcript={
            "url": f"s3://dummy-bucket/transcripts/seed-{seed_id}.pdf",
            "filename": f"{slug}-seed-{seed_id}.pdf",
        },
        key_insights=[
            f"Where budgets are actually shifting in {domain[0]}",
            f"The vendor evaluation criteria that actually matter for {domain[0]}",
            f"What leadership tracks to greenlight {domain[0]} initiatives",
        ],
        price=random.randint(20, 500),
        currency="INR",
        is_active=True,
        published_at=published_at,
    )


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    database_url = os.environ["DATABASE_URL"]

    engine = create_engine(database_url)
    with Session(engine) as session:
        session.add_all(build_transcript(i) for i in range(1, count + 1))
        session.commit()

    print(f"Inserted {count} sample transcripts.")


if __name__ == "__main__":
    main()
