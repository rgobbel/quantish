"""Sample marimo notebook demonstrating Claude API integration.

Run with: marimo edit notebooks/claude_demo.py
"""

import marimo

__generated_with = "0.17.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    from dotenv import load_dotenv
    import anthropic

    mo.md("# Claude API Integration Demo")
    return anthropic, load_dotenv, mo, os


@app.cell
def _(load_dotenv, mo, os):
    # Load environment variables from .env file
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key or api_key == "your_api_key_here":
        status = mo.md("""
        ⚠️ **API Key Not Set**

        Please add your Anthropic API key to `.env`:
        ```
        ANTHROPIC_API_KEY=sk-ant-api03-...
        ```

        Get your key from: https://console.anthropic.com/settings/keys
        """)
    else:
        status = mo.md("✅ API key loaded successfully")

    status
    return (api_key,)


@app.cell
def _(anthropic, api_key):
    # Initialize Claude client
    client = anthropic.Anthropic(api_key=api_key) if api_key else None
    return (client,)


@app.cell
def _(mo):
    mo.md("""
    ## Example 1: Simple Query

    Ask Claude a question about quantum physics:
    """)
    return


@app.cell
def _(mo):
    # Create an input for the user's question
    question = mo.ui.text_area(
        label="Your question:",
        value="Explain the concept of quantum superposition in simple terms.",
        full_width=True
    )
    question
    return (question,)


@app.cell
def _(client, mo, question):
    if client and question.value:
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": question.value}
                ]
            )

            result = mo.md(f"""
            **Claude's Response:**

            {response.content[0].text}
            """)
        except Exception as e:
            result = mo.md(f"❌ Error: {str(e)}")
    else:
        result = mo.md("_Enter a question above to get a response from Claude_")

    result
    return


@app.cell
def _(mo):
    mo.md("""
    ## Example 2: Code Generation

    Ask Claude to generate quantum circuit code:
    """)
    return


@app.cell
def _(mo):
    code_prompt = mo.ui.text_area(
        label="Code request:",
        value="Write a Qiskit circuit that creates a Bell state (entangled qubits)",
        full_width=True
    )
    code_prompt
    return (code_prompt,)


@app.cell
def _(client, code_prompt, mo):
    if client and code_prompt.value:
        try:
            code_response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": f"You are a quantum computing expert. {code_prompt.value}\n\nProvide clean, well-commented code."
                    }
                ]
            )

            code_result = mo.md(f"""
            **Generated Code:**

            {code_response.content[0].text}
            """)
        except Exception as e:
            code_result = mo.md(f"❌ Error: {str(e)}")
    else:
        code_result = mo.md("_Enter a code request above_")

    code_result
    return


@app.cell
def _(mo):
    mo.md("""
    ## Example 3: Multi-turn Conversation

    Have a conversation with Claude about your quantum physics project:
    """)
    return


@app.cell
def _(mo):
    # Conversation state and UI elements
    get_history, set_history = mo.state([])

    user_message = mo.ui.text_area(
        label="Your message:",
        placeholder="Ask about quantum mechanics, physics simulations, etc.",
        full_width=True
    )

    send_button = mo.ui.button(label="Send")

    mo.vstack([user_message, send_button])
    return get_history, send_button, set_history, user_message


@app.cell
def _(client, get_history, mo, send_button, set_history, user_message):
    if send_button.value and client and user_message.value:
        try:
            # Add user message to history
            current_history = list(get_history())
            current_history.append({
                "role": "user",
                "content": user_message.value
            })

            # Get Claude's response
            conv_response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=current_history,
                system="You are a helpful assistant specializing in quantum physics and quantum computing. You're helping with the Quantish physics simulation project."
            )

            # Add assistant response to history
            current_history.append({
                "role": "assistant",
                "content": conv_response.content[0].text
            })

            set_history(current_history)

            # Display conversation
            conversation_display = []
            for msg in current_history:
                role_emoji = "🧑" if msg["role"] == "user" else "🤖"
                role_name = "You" if msg["role"] == "user" else "Claude"
                conversation_display.append(
                    mo.md(f"**{role_emoji} {role_name}:** {msg['content']}")
                )

            conv_result = mo.vstack(conversation_display)
        except Exception as e:
            conv_result = mo.md(f"❌ Error: {str(e)}")
    elif len(get_history()) > 0:
        # Display existing conversation
        conversation_display = []
        for msg in get_history():
            role_emoji = "🧑" if msg["role"] == "user" else "🤖"
            role_name = "You" if msg["role"] == "user" else "Claude"
            conversation_display.append(
                mo.md(f"**{role_emoji} {role_name}:** {msg['content']}")
            )
        conv_result = mo.vstack(conversation_display)
    else:
        conv_result = mo.md("_Start a conversation by typing a message and clicking Send_")

    conv_result
    return


@app.cell
def _(mo):
    mo.md("""
    ## Example 4: Streaming Responses

    Get real-time streaming responses from Claude:
    """)
    return


@app.cell
def _(mo):
    stream_prompt = mo.ui.text_area(
        label="Streaming query:",
        value="Explain the mathematical formulation of quantum entanglement",
        full_width=True
    )
    stream_button = mo.ui.button(label="Stream Response")

    mo.vstack([stream_prompt, stream_button])
    return stream_button, stream_prompt


@app.cell
def _(client, mo, stream_button, stream_prompt):
    if stream_button.value and client and stream_prompt.value:
        try:
            stream_text = []

            with client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": stream_prompt.value}
                ]
            ) as stream:
                for text in stream.text_stream:
                    stream_text.append(text)

            stream_result = mo.md(f"""
            **Streaming Response:**

            {''.join(stream_text)}
            """)
        except Exception as e:
            stream_result = mo.md(f"❌ Error: {str(e)}")
    else:
        stream_result = mo.md("_Click the button above to stream a response_")

    stream_result
    return


@app.cell
def _(mo):
    mo.md("""
    ---

    ## Tips for Using Claude with Marimo

    1. **Environment Variables**: Always use `.env` for API keys
    2. **Error Handling**: Wrap API calls in try-except blocks
    3. **Token Limits**: Be mindful of `max_tokens` for cost control
    4. **Model Selection**: Use `claude-sonnet-4-5-20250929` for best results
    5. **System Prompts**: Add domain-specific context for better responses
    6. **State Management**: Use `mo.state()` for conversation history

    ### Available Models

    - `claude-sonnet-4-5-20250929` - Most capable (recommended)
    - `claude-opus-4-20250514` - Highest intelligence
    - `claude-3-5-sonnet-20241022` - Previous generation

    ### Useful Resources

    - [Anthropic API Documentation](https://docs.anthropic.com/)
    - [Marimo Documentation](https://docs.marimo.io/)
    - [Claude Pricing](https://www.anthropic.com/pricing)
    """)
    return


if __name__ == "__main__":
    app.run()
