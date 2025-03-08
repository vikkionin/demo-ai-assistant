import streamlit as st
import textwrap
from concurrent.futures import ThreadPoolExecutor
from snowflake.core import Root  # requires snowflake>=0.8.0
from snowflake.cortex import complete


st.set_page_config(page_title="Streamlit assistant", page_icon="💬")


# -----------------------------------------------------------------------------
# Set things up.


@st.cache_resource
def get_session():
    return st.connection("snowflake").session()


root = Root(get_session())
executor = ThreadPoolExecutor(max_workers=5)

MODEL = "claude-3-5-sonnet"

DB = "MAIN"
SCHEMA = "PUBLIC"
DOCSTRINGS_SEARCH_SERVICE = "STREAMLIT_DOCSTRINGS_SEARCH_SERVICE"
PAGES_SEARCH_SERVICE = "STREAMLIT_DOCS_PAGES_SEARCH_SERVICE"
STREAMLIT_VERSION = "1.43.0"
HISTORY_LENGTH = 5
SUMMARIZE_OLD_HISTORY = True
DOCSTRINGS_CONTEXT_LEN = 5
PAGES_CONTEXT_LEN = 5

DEBUG_MODE = st.query_params.get("debug", "false").lower() == "true"

INSTRUCTIONS = textwrap.dedent("""
    - You are a helpful AI chat assistant focused on answering quesions about Streamlit and general Python.
    - You will be given extra information provided inside tags like this <foo></foo>.
    - Use context and history to provide a coherent answer. But only use them if they make sense.
    - Be concise.
    - Do not hallucinate. If you don't know, just say "I don't know the answer to that question."
    - Assume the user is a junior developer.
    - Provide examples.
    - Respond with markdown.
    - Avoid experimental and private APIs.
    - Don't say things like "according to the provided context".
    - Streamlit is a product of Snowflake.
""")


def build_prompt(**kwargs):
    prompt = []

    for name, contents in kwargs.items():
        if contents:
            prompt.append(f"<{name}>\n{contents}\n</{name}>")

    prompt_str = "\n".join(prompt)

    return prompt_str


def build_question_prompt(question):
    old_history = st.session_state.messages[:-HISTORY_LENGTH]
    recent_history = st.session_state.messages[-HISTORY_LENGTH:]

    if recent_history:
        recent_history_str = history_to_text(recent_history)
    else:
        recent_history_str = None

    tasks = []

    if SUMMARIZE_OLD_HISTORY and old_history:
        tasks.append(
            ("old_message_summary", generate_chat_summary, (old_history,)))

    if PAGES_CONTEXT_LEN:
        tasks.append(
            ("documentation_pages", search_relevant_pages, (question,)))

    if DOCSTRINGS_CONTEXT_LEN:
        tasks.append(
            ("command_docstrings", search_relevant_docstrings, (question,)))

    results = executor.map(lambda task: (task[0], task[1](*task[2])), tasks)
    context = {k: v for k, v in results}

    return build_prompt(
        instructions=INSTRUCTIONS,
        **context,
        recent_messages=recent_history_str,
        question=question,
    )


def generate_chat_summary(messages):
    prompt = build_prompt(
        instructions="Summarize this conversation as concisely as possible.",
        conversation=history_to_text(messages),
    )

    return complete(MODEL, prompt, session=get_session())


def history_to_text(chat_history):
    return "\n".join(f"[{h['role']}]: {h['content']}" for h in chat_history)


def search_relevant_pages(query):
    cortex_search_service = (
        root
        .databases[DB]
        .schemas[SCHEMA]
        .cortex_search_services[PAGES_SEARCH_SERVICE]
    )

    context_documents = cortex_search_service.search(
        query,
        columns=["PAGE_URL", "PAGE_CHUNK"],
        filter={},
        limit=PAGES_CONTEXT_LEN,
    )

    results = context_documents.results

    context = [
        f"[Document {i}]: {
            row['PAGE_CHUNK']}"
        for i, row in enumerate(results)
    ]
    context_str = "\n".join(context)

    return context_str


def search_relevant_docstrings(query):
    cortex_search_service = (
        root.databases[DB]
        .schemas[SCHEMA]
        .cortex_search_services[DOCSTRINGS_SEARCH_SERVICE]
    )

    context_documents = cortex_search_service.search(
        query,
        columns=["STREAMLIT_VERSION", "COMMAND_NAME", "DOCSTRING_CHUNK"],
        filter={"@eq": {"STREAMLIT_VERSION": "latest"}},
        limit=DOCSTRINGS_CONTEXT_LEN,
    )

    results = context_documents.results

    context = [
        f"[Document {i}]: {row['DOCSTRING_CHUNK']}"
        for i, row in enumerate(results)
    ]
    context_str = "\n".join(context)

    return context_str


def send_telemetry(**kwargs):
    # TODO: Implement this.
    pass


def show_feedback_controls(message_index):
    st.write("")

    with st.popover("How did I do?"):
        with st.form(key=f"feedback-{message_index}", border=False):
            st.markdown(":small[Rating]")
            rating = st.feedback("stars")

            details = st.text_area("More information")

            if st.checkbox("Include chat history with my feedback", True):
                relevant_history = st.session_state.messages[:message_index]
            else:
                relevant_history = []

            st.form_submit_button("Send feedback")

            # TODO: Send feedback and history.
            st.caption("PS: This is not connected to anything yet!")


# -----------------------------------------------------------------------------
# Draw the UI.

cols = st.columns([3, 1], vertical_alignment="bottom")

with cols[0]:
    st.title("Streamlit assistant")

with cols[1]:
    clear_conversation = st.button(
        "Restart",
        icon=":material/refresh:",
        use_container_width=True,
    )

if clear_conversation or "messages" not in st.session_state:
    st.session_state.messages = []

st.write(
    ":small["
    ":material/info: "
    "This app uses "
    "[Snowflake Cortex](https://docs.snowflake.com/en/guides-overview-ai-features) "
    "and is [open source](#)! "
    "]"
)

# Show a fake question from the assistant to get the user started.
with st.chat_message("assistant"):
    st.markdown("Hello, how may I help you?")

# Display chat messages from history as speech bubbles.
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant":
            show_feedback_controls(i)

if question := st.chat_input("Ask a question..."):
    # When the user posts a message...

    # Streamlit's Markdown engine interprets "$" as LaTeX code (used to
    # display math). The line below fixes it.
    question = question.replace("$", r"\$")

    # Display message as a speech bubble.
    with st.chat_message("user"):
        st.markdown(question)

    # Display assistant response as a speech bubble.
    with st.chat_message("assistant"):
        question = question.replace("'", "")

        # Build a detailed prompt.
        if DEBUG_MODE:
            with st.status("Computing prompt...") as status:
                full_prompt = build_question_prompt(question)
                st.code(full_prompt)
                status.update(label="Prompt computed")
        else:
            with st.expander("Researching..."):
                full_prompt = build_question_prompt(question)

        # Send prompt to LLM.
        with st.spinner("Thinking..."):
            response_gen = complete(
                MODEL,
                full_prompt,
                stream=True,
                session=get_session(),
            )

        # Stream the LLM response.
        response = st.write_stream(response_gen)

        # Add messages to chat history.
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state.messages.append(
            {"role": "assistant", "content": response})

        # Other stuff.
        show_feedback_controls(len(st.session_state.messages) - 1)
        send_telemetry(question=question, response=response)
