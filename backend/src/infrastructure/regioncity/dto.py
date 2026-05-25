from pydantic import BaseModel, Field


class RegionCityTaskListItem(BaseModel):
    task_id: str = Field(alias="taskID")
    task_type_id: int = Field(alias="taskTypeID")
    status: int
    map_object_id: str | None = Field(default=None, alias="mapObjectID")
    last_status_change_date: str | None = Field(default=None, alias="lastStatusChangeDate")
    title: str | None = None
    address: str | None = None
    description: str | None = None
    custom_status_id: int | None = Field(default=None, alias="customStatusID")
    subscriber_id: str | None = Field(default=None, alias="subscriberID")
    longitude: float | None = None
    latitude: float | None = None
    start_date: str | None = Field(default=None, alias="startDate")
    deadline: str | None = None
    creation_date: str | None = Field(default=None, alias="creationDate")
    custom_field_form_items: list[dict] = Field(default_factory=list, alias="customFieldFormItems")
