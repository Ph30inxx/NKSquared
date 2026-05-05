from pydantic import BaseModel


class CallSession(BaseModel):
    call_id: str
    user_id: int
    session_id: str           # Agno conversation session_id — links to chat_conversations
    user_id_missing: bool = False  # guard: set when variableValues absent from Vapi start
    turn_count: int = 0
