#!/usr/bin/env python3
"""
Run script for Resume Career Consultant MVP
"""
import uvicorn
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    print("🚀 Starting Resume Career Consultant MVP...")
    print("📍 Visit: http://localhost:8000")
    print("💡 Press Ctrl+C to stop")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
