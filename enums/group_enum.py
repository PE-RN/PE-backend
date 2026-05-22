from enum import Enum


class GroupNameEnum(str, Enum):
    ANONYMOUS = "anonymous"
    TEST = "test"
    DEVELOPER = "developer"
    ADMIN = "admin"
    AUTHENTICATED = "authenticated"
