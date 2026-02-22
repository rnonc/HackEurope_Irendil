from pydantic import BaseModel
from typing import List



class Stool(BaseModel):
    token : str
    stool : dict[str,float]