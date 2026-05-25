from enum import Enum


class SubjectType(str, Enum):
    DISTRICT = "district"
    HOUSE = "house"
    ENTRANCE = "entrance"


class ChannelType(str, Enum):
    MAX = "max"


class AdminRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    DISTRICT_ADMIN = "district_admin"


class Source(str, Enum):
    REGIONCITY = "regioncity"


class EventType(str, Enum):
    CLEANING_COMPLETED = "cleaning.completed"
