from .thresholds import THRESHOLD_PROMPTS
from .screening import SCREENING_PROMPTS

THRESHOLD_PROMPTS.update(SCREENING_PROMPTS)

__all__ = ["THRESHOLD_PROMPTS"]
