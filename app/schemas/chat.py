from pydantic import BaseModel
from typing import Optional

class ChatMessage(BaseModel):
    role: str  # "assistant" or "user"
    content: str

class ChatRequest(BaseModel):
    conversation_id: int
    message: str

class ChatResponse(BaseModel):
    message_id: int
    role: str
    content: str
    created_at: str
