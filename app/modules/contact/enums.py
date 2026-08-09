import enum


class ContactPlatform(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    BRAIDER = "BRAIDER"


class ContactPurpose(str, enum.Enum):
    GENERAL = "GENERAL"
    PARTNER = "PARTNER"
    PRICING = "PRICING"
    FAQS = "FAQS"
