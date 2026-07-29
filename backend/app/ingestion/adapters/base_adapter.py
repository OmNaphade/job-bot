from abc import ABC, abstractmethod
from typing import List

from app.ingestion.models import JobCandidate


class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self) -> List[JobCandidate]:
        raise NotImplementedError
