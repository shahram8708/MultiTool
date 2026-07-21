"""
Gemini AI service.

Provides a client factory and message-sending function that integrates
with the Google Gemini generative AI API. Maintains a 5-message context
window loaded from the database and passes system instructions on the
first turn of each conversation.
"""

import concurrent.futures
from typing import Optional

from flask import current_app
from google import genai
from google.genai import types

from app.extensions import db
from app.models.message import Message


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def get_gemini_client() -> genai.Client:
    """Return a configured ``google.genai.Client`` using the app's API key."""
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError(
            'GEMINI_API_KEY is not set. Add it to your .env file or environment.'
        )
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Core messaging
# ---------------------------------------------------------------------------

def send_message(
    chat_id: int,
    user_text: str,
    file_parts: list = None,
    include_system_instruction: Optional[bool] = None,
    exclude_message_id: Optional[int] = None,
) -> str:
    """Send a user message to Gemini and return the assistant's response text.

    Parameters
    ----------
    chat_id:
        The database ID of the current :class:`Chat`.
    user_text:
        The plain-text content of the user's message.
    file_parts:
        An optional list of ``google.genai.types.Part`` objects (images,
        uploaded files, etc.) to include with the current user turn.

    Returns
    -------
    str
        The assistant's response in Markdown.

    The function builds a context window of the most recent **5 messages**
    already persisted for *chat_id* (before the current user message is
    saved).  On the very first turn (no prior messages) the chat's
    ``system_instruction`` is included via ``GenerateContentConfig``.
    """
    from app.models.chat import Chat  # deferred to avoid circular imports

    try:
        client = get_gemini_client()
        model_name = current_app.config.get('GEMINI_MODEL', 'gemini-2.0-flash')

        # Load the chat record for its system instruction
        chat = db.session.get(Chat, chat_id)
        if chat is None:
            raise ValueError(f'Chat {chat_id} not found')

        # ---- Build the context window (last 5 persisted messages) --------
        query = Message.query.filter_by(chat_id=chat_id)
        if exclude_message_id is not None:
            query = query.filter(Message.id != exclude_message_id)

        recent_messages = (
            query
            .order_by(Message.timestamp.desc())
            .limit(5)
            .all()
        )
        # Reverse so they are in chronological order
        recent_messages = list(reversed(recent_messages))

        is_first_turn = len(recent_messages) == 0
        should_include_system_instruction = (
            is_first_turn if include_system_instruction is None else include_system_instruction
        )

        # ---- Assemble contents list for the API call ---------------------
        contents: list[types.Content] = []

        for msg in recent_messages:
            role = 'user' if msg.role == 'user' else 'model'
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)],
                )
            )

        # Current user turn
        current_parts: list[types.Part] = []
        if file_parts:
            current_parts.extend(file_parts)
        if user_text and user_text.strip():
            current_parts.append(types.Part.from_text(text=user_text))
        elif not current_parts:
            current_parts.append(types.Part.from_text(text='Please analyze the provided input.'))

        contents.append(
            types.Content(role='user', parts=current_parts)
        )

        # ---- Build generation config -------------------------------------
        gen_config = None
        if should_include_system_instruction and chat.system_instruction:
            gen_config = types.GenerateContentConfig(
                system_instruction=chat.system_instruction,
            )

        # ---- Call the API with a timeout ---------------------------------
        def _call_api():
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=gen_config,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_api)
            try:
                response = future.result(timeout=120)
            except concurrent.futures.TimeoutError:
                current_app.logger.error(
                    'Gemini API call timed out after 120 s for chat %s', chat_id
                )
                return (
                    'The AI took too long to respond. Please try again with a '
                    'shorter message or simpler request.'
                )

        # Extract text from the response
        if response and response.text:
            return response.text
        else:
            current_app.logger.warning(
                'Empty response from Gemini for chat %s', chat_id
            )
            return 'I received an empty response. Please try rephrasing your message.'

    except genai.errors.ClientError as exc:
        current_app.logger.error('Gemini client error for chat %s: %s', chat_id, exc)
        return f'An API error occurred: {exc}'

    except genai.errors.ServerError as exc:
        current_app.logger.error('Gemini server error for chat %s: %s', chat_id, exc)
        return (
            'The AI service is temporarily unavailable. Please try again in a moment.'
        )

    except Exception as exc:
        current_app.logger.exception(
            'Unexpected error in send_message for chat %s', chat_id
        )
        return f'An unexpected error occurred: {exc}'
