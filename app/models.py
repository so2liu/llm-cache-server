from typing import Optional, Union
from pydantic import BaseModel


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list
    temperature: float = 0
    stream: bool = False
    tool_choice: Optional[Union[str, dict]] = None
    tools: Optional[list] = None
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    n: int = 1
    stop: Optional[Union[str, list]] = None
    presence_penalty: float = 0
    frequency_penalty: float = 0
    logit_bias: Optional[dict] = None
    user: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list
    usage: dict
