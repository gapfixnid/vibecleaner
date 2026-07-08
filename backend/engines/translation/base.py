from abc import ABC, abstractmethod
import numpy as np
from typing import List, Any

class BaseTranslator(ABC):


    @abstractmethod
    def check_connection(self) -> bool:
        """Check if the translation backend is online."""
        pass

    @abstractmethod
    def translate_blocks(self, blocks: List[Any], source_lang: str, target_lang: str, image: np.ndarray = None) -> List[Any]:
        """Translate a list of text blocks."""
        pass
