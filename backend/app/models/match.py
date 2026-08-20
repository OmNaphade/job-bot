from app.models.job import JobBase


class JobMatch(JobBase):
    id: int
    match_score: float
