
from pydantic import BaseModel, Field, field_validator
from typing import Literal, List, Optional, Any

Op = Literal["=", "!=", ">", ">=", "<", "<=", "IN", "BETWEEN"]

AllowedFields = {
    "users": {"user_id","name","age","gender","region","signup_dt","is_employee","is_test_user","segment"},
    "transactions": {"user_id","event_id","amount","txn_dt","product_code","channel"}
}

class Filter(BaseModel):
    field: str
    op: Op
    value: Any

    @field_validator("field")
    @classmethod
    def field_whitelist(cls, v):
        allowed = set().union(*AllowedFields.values())
        if v not in allowed:
            raise ValueError(f"field not allowed: {v}")
        return v

class Join(BaseModel):
    with_: Literal["transactions"] = Field(alias="with")
    on: str = "users.user_id = transactions.user_id"
    type: Literal["inner","left"] = "inner"
    aggregations: Optional[list] = None
    having: Optional[List[Filter]] = None

class QueryDSL(BaseModel):
    target: Literal["users"] = "users"
    filters: List[Filter] = []
    joins: List[Join] = []
    limit: Optional[int] = None
