from typing import List

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate


class SampleAdapter(BaseAdapter):
    def fetch(self) -> List[JobCandidate]:
        return [
            JobCandidate(
                title="Backend Engineer",
                company="Example Corp",
                location="Remote",
                link="https://example.com/jobs/backend-engineer",
                source="sample",
            ),
            JobCandidate(
                title="Flutter Developer",
                company="Example Labs",
                location="Pune",
                link="https://example.com/jobs/flutter-developer",
                source="sample",
            ),
        ]
