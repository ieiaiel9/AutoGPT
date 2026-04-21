"""Base class for memory providers."""
import abc

from autogpt.config import AbstractSingleton, Config
from autogpt.llm_utils import create_embedding_with_ada

cfg = Config()


def get_ada_embedding(text):
    text = text.replace("\n", " ")
    return create_embedding_with_ada(text)


class MemoryProviderSingleton(AbstractSingleton):
    @abc.abstractmethod
    def add(self, data):
        pass

    @abc.abstractmethod
    def get(self, data):
        pass

    @abc.abstractmethod
    def clear(self):
        pass

    @abc.abstractmethod
    def get_relevant(self, data, num_relevant=5):
        pass

    @abc.abstractmethod
    def get_stats(self):
        pass
