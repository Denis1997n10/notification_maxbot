from pydantic import BaseModel


class PublicSubjectPageDTO(BaseModel):
    subject_id: str
    events: list[dict]
