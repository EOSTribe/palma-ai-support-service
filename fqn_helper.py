from dataclasses import dataclass

@dataclass(frozen=True)
class FQN:
    """Domain entity representing a fully qualified name."""
    namespace: str
    name: str

class FQNHelper:
    """Utility for converting raw FQN strings to :class:`FQN` entities."""

    @staticmethod
    def map(raw_fqn: str) -> FQN:
        """Convert a dotted string into an :class:`FQN` entity."""
        if not isinstance(raw_fqn, str) or not raw_fqn:
            raise ValueError("raw_fqn must be a non-empty string")

        parts = raw_fqn.split('.')
        if len(parts) == 1:
            return FQN(namespace="", name=parts[0])

        return FQN(namespace='.'.join(parts[:-1]), name=parts[-1])
