"""Conversation repository"""
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import Conversation, Message
import logging

logger = logging.getLogger(__name__)

class ConversationRepository:
    @staticmethod
    def create_conversation(db: Session, user_id: int) -> Conversation:
        """Create new conversation"""
        conv = Conversation(user_id=user_id, status="active")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv
    
    @staticmethod
    def get_conversation(db: Session, conversation_id: int) -> Conversation:
        """Get conversation by ID"""
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()
    
    @staticmethod
    def get_user_conversations(db: Session, user_id: int) -> list:
        """Get all conversations for user"""
        return db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).all()
    
    @staticmethod
    def add_message(db: Session, conversation_id: int, role: str, content: str) -> Message:
        """Add message to conversation"""
        message = Message(conversation_id=conversation_id, role=role, content=content)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    
    @staticmethod
    def get_conversation_messages(db: Session, conversation_id: int) -> list:
        """Get all messages in conversation"""
        return db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    
    @staticmethod
    def update_conversation_status(db: Session, conversation_id: int, status: str):
        """Update conversation status"""
        conv = ConversationRepository.get_conversation(db, conversation_id)
        if conv:
            conv.status = status
            conv.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(conv)
        return conv
