from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class GrantsSearchParams(BaseModel):
    keyword: str = Field(default="", description="Keyword to search for")
    date_range: str = Field(default="30", description="Date range to search in (e.g., '30' for 30 days)")
    opp_statuses: str = Field(default="forecasted|posted", description="Opportunity statuses to include (e.g., 'forecasted|posted')")
    rows: int = Field(default=5000, description="Number of rows to return")
    sort_by: str = Field(default="openDate|desc", description="Sort order (e.g., 'openDate|desc')")

class GrantOpportunity(BaseModel):
    id: str
    number: str
    title: str
    agency_code: str
    agency: str
    open_date: str
    close_date: Optional[str] = None
    status: str
    doc_type: str
    cfda_list: List[str]

class GrantsResponse(BaseModel):
    success: bool
    message: str
    count: Optional[int] = None
    data: Optional[Union[List[GrantOpportunity], Dict[str, Any], List[Dict[str, Any]]]] = None
    error: Optional[str] = None 