from enum import StrEnum

from sqlalchemy import Enum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


def enum_type(enum_class: type[StrEnum]) -> Enum:
    return Enum(
        enum_class,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
        validate_strings=True,
    )
