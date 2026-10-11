from __future__ import annotations
import re
from pydantic import BaseModel, Field
from ..models.schemas import Story
class PhotoBrief(BaseModel):
    who: list[str] = Field(default_factory=list); where: str = ""; what_event: str = ""; when: str = ""; shot_type: str = "illustration"; must_show: list[str] = Field(default_factory=list); must_not_show: list[str] = Field(default_factory=list); search_queries_pl: list[str] = Field(default_factory=list); search_queries_en: list[str] = Field(default_factory=list); is_real_event: bool = False; real_people: list[str] = Field(default_factory=list)
def build_photo_brief(story: Story) -> PhotoBrief:
    text=" ".join(filter(None,[story.headline,story.lead,story.body]))
    people=re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻ-]+\s+[A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻ-]+",text)
    real=bool(re.search(r"\b(wczoraj|dziś|202\d|wydarzen|atak|wybor|konferenc|mecz|pożar|wypadek)\w*\b",text,re.I))
    return PhotoBrief(who=list(dict.fromkeys(people)),what_event=story.headline,shot_type="archival" if real else "illustration",must_show=[story.headline],search_queries_pl=[story.headline],search_queries_en=[story.headline],is_real_event=real,real_people=list(dict.fromkeys(people)))
