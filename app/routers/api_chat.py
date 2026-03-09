"""Chat API routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.db import get_db
from app.repositories.conversations import ConversationRepository
from app.schemas.chat import ChatRequest, ChatResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/chat/message")
async def chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Process chat message"""
    try:
        # Save user message
        msg = ConversationRepository.add_message(
            db,
            request.conversation_id,
            "user",
            request.message
        )
        
        # For MVP, just echo back or provide next step guidance
        if "резюме" in request.message.lower() and "вакансия" not in request.message.lower():
            response_text = "Спасибо за резюме! Теперь пожалуйста, загрузите описание вакансии."
            role = "assistant"
        elif "вакансия" in request.message.lower():
            response_text = "Отлично! Анализирую ваш профиль и требования вакансии. Это может занять момент..."
            role = "assistant"
        else:
            response_text = f"Получил: {request.message[:50]}... Пожалуйста, загрузите резюме или описание вакансии."
            role = "assistant"
        
        # Save assistant response
        resp_msg = ConversationRepository.add_message(
            db,
            request.conversation_id,
            role,
            response_text
        )
        
        return {
            "status": "ok",
            "message_id": resp_msg.id,
            "content": response_text,
            "created_at": resp_msg.created_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Error in chat_message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chat/{conversation_id}")
async def get_chat(conversation_id: int, db: Session = Depends(get_db)):
    """Get chat history"""
    try:
        conv = ConversationRepository.get_conversation(db, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = ConversationRepository.get_conversation_messages(db, conversation_id)
        messages_data = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
        
        return {"messages": messages_data}
    except Exception as e:
        logger.error(f"Error in get_chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
