from typing import List

from app.ingestion.models import JobCandidate


class DedupService:
    """Filters duplicate links within a single ingestion batch.

    Cross-run dedup is handled at the persistence layer via the
    `jobs.link UNIQUE` constraint (see JobRepository.create_job_if_new),
    which is the only place that can do it atomically.
    """

    def filter_new(self, candidates: List[JobCandidate]) -> List[JobCandidate]:
        seen_links: set[str] = set()
        deduped: List[JobCandidate] = []
        for candidate in candidates:
            if candidate.link in seen_links:
                continue
            seen_links.add(candidate.link)
            deduped.append(candidate)
        return deduped
