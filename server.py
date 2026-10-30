"""
JARVIS 24/7 Server Engine & Telephony Gateway
Run with: uvicorn server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
from fastapi import FastAPI, Form, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from twilio.twiml.voice_response import VoiceResponse, Gather

import config
from assistant import brain

app = FastAPI(title="JARVIS Server Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    user_id: str = "Henderson"  # Henderson or Jenna


class CallUserRequest(BaseModel):
    message: str
    target_phone_number: str


@app.get("/health")
def health_check():
    return {"status": "online", "model": config.OLLAMA_CHAT_MODEL}


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    """Chat endpoint for browsers, phone web apps, and smartwatch integrations."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    
    reply = brain.process(req.message, user_id=req.user_id)
    return {"reply": reply, "user_id": req.user_id}


# --------------------------------------------------------------------------
# Telephony Webhooks (Twilio Inbound / Outbound Calls)
# --------------------------------------------------------------------------

@app.post("/voice/inbound")
async def handle_inbound_call(From: str = Form("Unknown")):
    """Handles incoming calls dialed to JARVIS's phone number."""
    response = VoiceResponse()
    
    gather = Gather(
        input="speech",
        action="/voice/process-screening",
        method="POST",
        speech_timeout="auto",
        speech_model="phone_call",
    )
    gather.say(
        "Hello. You have reached JARVIS. Please state your name and the reason for your call.",
        voice="Polly.Amy",
    )
    
    response.append(gather)
    response.say("I did not receive a response. Goodbye.", voice="Polly.Amy")
    response.hangup()
    
    return Response(content=str(response), media_type="application/xml")


@app.post("/voice/process-screening")
async def process_screening(SpeechResult: str = Form(""), From: str = Form("Unknown")):
    """Screen caller response and alert Henderson."""
    response = VoiceResponse()
    
    if SpeechResult:
        prompt = f"Call received from {From}. Caller said: '{SpeechResult}'. Summarize who called and why."
        brain.process(prompt, user_id="Henderson")
        response.say("Thank you. I have notified Henderson.", voice="Polly.Amy")
    else:
        response.say("Thank you for calling. Goodbye.", voice="Polly.Amy")
        
    response.hangup()
    return Response(content=str(response), media_type="application/xml")


@app.post("/api/voice/call-me")
async def initiate_outbound_call(req: CallUserRequest):
    """Triggers an outbound call to Henderson or Jenna."""
    try:
        from twilio.rest import Client
        
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = os.environ.get("TWILIO_PHONE_NUMBER")
        
        if not all([account_sid, auth_token, from_number]):
            raise HTTPException(status_code=500, detail="Twilio credentials missing in environment.")
            
        client = Client(account_sid, auth_token)
        twiml_payload = f"<Response><Say voice='Polly.Amy'>{req.message}</Say></Response>"
        
        call = client.calls.create(
            twiml=twiml_payload,
            to=req.target_phone_number,
            from_=from_number
        )
        return {"status": "initiated", "call_sid": call.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))