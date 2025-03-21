# Copyright 2025 Snowflake Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
import datetime
import textwrap
import time

import streamlit as st
from snowflake.core import Root  # requires snowflake>=0.8.0
from snowflake.cortex import complete


st.set_page_config(page_title="Streamlit assistant", page_icon="💬")

# -----------------------------------------------------------------------------
# Set things up.


@st.cache_resource(ttl="12h")
def get_session():
    return st.connection("snowflake").session()


root = Root(get_session())
executor = ThreadPoolExecutor(max_workers=5)

MODEL = "claude-3-5-sonnet"

DB = "ST_ASSISTANT"
SCHEMA = "PUBLIC"
DOCSTRINGS_SEARCH_SERVICE = "STREAMLIT_DOCSTRINGS_SEARCH_SERVICE"
PAGES_SEARCH_SERVICE = "STREAMLIT_DOCS_PAGES_SEARCH_SERVICE"
HISTORY_LENGTH = 5
SUMMARIZE_OLD_HISTORY = True
DOCSTRINGS_CONTEXT_LEN = 10
PAGES_CONTEXT_LEN = 10
MIN_TIME_BETWEEN_REQUESTS = datetime.timedelta(seconds=3)

CORTEX_URL = (
    "https://docs.snowflake.com/en/guides-overview-ai-features"
    "?utm_source=streamlit"
    "&utm_medium=referral"
    "&utm_campaign=streamlit-demo-apps"
    "&utm_content=streamlit-assistant"
)

GITHUB_URL = "https://github.com/streamlit/streamlit-assistant"

DEBUG_MODE = st.query_params.get("debug", "false").lower() == "true"

INSTRUCTIONS = textwrap.dedent("""
    - You are a helpful AI chat assistant focused on answering quesions about
      Streamlit, Streamlit Community Cloud, and general Python.
    - You will be given extra information provided inside tags like this
      <foo></foo>.
    - Use context and history to provide a coherent answer.
    - Use markdown such as headers (starting with ###), code blocks, bullet
      points, 3-space indentation for sub bullets, and backticks for inline
      code and markdown features like icon names.
    - Assume the user is a newbie.
    - Write paragraphs of explanation, as if you're writing documentation.
    - Offer alternatives where they exist.
    - Provide examples.
    - Include related links throughout the text and at the bottom.
    - Avoid experimental and private APIs.
    - Don't say things like "according to the provided context".
    - If you don't know, just say "I don't know the answer to that question."
    - Streamlit is a product of Snowflake.
""")


def build_prompt(**kwargs):
    """Builds a prompt string with the kwargs are HTML-like tags.

    For example, this:

        build_prompt(foo="1\n2\n3", bar="4\n5\n6")

    ...returns:

        '''
        <foo>
        1
        2
        3
        </foo>
        <bar>
        4
        5
        6
        </bar>
        '''
    """
    prompt = []

    for name, contents in kwargs.items():
        if contents:
            prompt.append(f"<{name}>\n{contents}\n</{name}>")

    prompt_str = "\n".join(prompt)

    return prompt_str


# Just some little objects to make tasks easier to read.
TaskInfo = namedtuple("TaskInfo", ["name", "function", "args"])
TaskResult = namedtuple("TaskResult", ["name", "result"])


def build_question_prompt(question):
    """Fetches info from different services and creates the prompt string."""
    old_history = st.session_state.messages[:-HISTORY_LENGTH]
    recent_history = st.session_state.messages[-HISTORY_LENGTH:]

    if recent_history:
        recent_history_str = history_to_text(recent_history)
    else:
        recent_history_str = None

    # Fetch information from different services in parallel.
    task_infos = []

    if SUMMARIZE_OLD_HISTORY and old_history:
        task_infos.append(
            TaskInfo(
                name="old_message_summary",
                function=generate_chat_summary,
                args=(old_history,),
            )
        )

    if PAGES_CONTEXT_LEN:
        task_infos.append(
            TaskInfo(
                name="documentation_pages",
                function=search_relevant_pages,
                args=(question,),
            )
        )

    if DOCSTRINGS_CONTEXT_LEN:
        task_infos.append(
            TaskInfo(
                name="command_docstrings",
                function=search_relevant_docstrings,
                args=(question,),
            )
        )

    results = executor.map(
        lambda task_info: TaskResult(
            name=task_info.name,
            result=task_info.function(*task_info.args),
        ),
        task_infos,
    )

    context = {name: result for name, result in results}

    return build_prompt(
        instructions=INSTRUCTIONS,
        **context,
        recent_messages=recent_history_str,
        question=question,
    )


def generate_chat_summary(messages):
    """Summarizes the chat history in `messages`."""
    prompt = build_prompt(
        instructions="Summarize this conversation as concisely as possible.",
        conversation=history_to_text(messages),
    )

    return complete(MODEL, prompt, session=get_session())


def history_to_text(chat_history):
    """Converts chat history into a string."""
    return "\n".join(f"[{h['role']}]: {h['content']}" for h in chat_history)


def search_relevant_pages(query):
    """Searches the markdown contents of Streamlit's documentation."""
    cortex_search_service = (
        root.databases[DB].schemas[SCHEMA].cortex_search_services[PAGES_SEARCH_SERVICE]
    )

    context_documents = cortex_search_service.search(
        query,
        columns=["PAGE_URL", "PAGE_CHUNK"],
        filter={},
        limit=PAGES_CONTEXT_LEN,
    )

    results = context_documents.results

    context = [f"[{row['PAGE_URL']}]: {row['PAGE_CHUNK']}" for row in results]
    context_str = "\n".join(context)

    return context_str


def search_relevant_docstrings(query):
    """Searches the docstrings of Streamlit's commands."""
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
        f"[Document {i}]: {row['DOCSTRING_CHUNK']}" for i, row in enumerate(results)
    ]
    context_str = "\n".join(context)

    return context_str


def get_response(prompt):
    return complete(
        MODEL,
        prompt,
        stream=True,
        session=get_session(),
    )


def send_telemetry(**kwargs):
    """Records some telemetry about questions being asked."""
    # TODO: Implement this.
    pass


def show_feedback_controls(message_index):
    """Shows the "How did I do?" control."""
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
    st.title("Streamlit assistant", anchor=False)

with cols[1]:
    clear_conversation = st.button(
        "Restart",
        icon=":material/refresh:",
        use_container_width=True,
    )

if clear_conversation or "messages" not in st.session_state:
    st.session_state.messages = []

if "prev_question_timestamp" not in st.session_state:
    st.session_state.prev_question_timestamp = datetime.datetime.fromtimestamp(
        0)

with st.expander(
    ":material/balance: "
    "This is an AI chatbot, so it may hallucinate. Expand to see legal "
    "disclaimer."
):
    st.write("""
        This AI chatbot is powered by Snowflake and public Streamlit
        information. Answers may be inaccurate, inefficient, or biased.
        Any use or decisions based on such answers should include reasonable
        practices including human oversight to ensure they are safe,
        accurate, and suitable for your intended purpose. Streamlit is not
        liable for any actions, losses, or damages resulting from the use
        of the chatbot. Do not enter any private, sensitive, personal, or
        regulated data. By using this chatbot, you acknowledge and agree
        that input you provide and answers you receive (collectively,
        “Content”) may be used by Snowflake to provide, maintain, develop,
        and improve their respective offerings. For more
        information on how Snowflake may use your Content, see
        https://streamlit.io/terms-of-service.
    """)

st.info(
    ":small["
    ":material/info: "
    "This app uses "
    f"[Snowflake Cortex]({CORTEX_URL}) "
    f"and is [fully open source]({GITHUB_URL})! "
    "]"
)

# Show a fake question from the assistant to get the user started.
with st.chat_message("assistant"):
    st.markdown("Hello, how may I help you?")

# Display chat messages from history as speech bubbles.
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.container()  # Fix ghost message bug.

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
        st.text(question)

    # Display assistant response as a speech bubble.
    with st.chat_message("assistant"):
        with st.spinner("Waiting..."):
            # Rate-limit the input if needed.
            question_timestamp = datetime.datetime.now()
            time_diff = question_timestamp - st.session_state.prev_question_timestamp
            st.session_state.prev_question_timestamp = question_timestamp

            if time_diff < MIN_TIME_BETWEEN_REQUESTS:
                time.sleep(time_diff.seconds + time_diff.microseconds * 0.001)

            question = question.replace("'", "")

        # Build a detailed prompt.
        if DEBUG_MODE:
            with st.status("Computing prompt...") as status:
                full_prompt = build_question_prompt(question)
                st.code(full_prompt)
                status.update(label="Prompt computed")
        else:
            with st.spinner("Researching..."):
                full_prompt = build_question_prompt(question)

        # Send prompt to LLM.
        with st.spinner("Thinking..."):
            response_gen = get_response(full_prompt)

        # Put everything after the spinners in a container to fix the
        # ghost message bug.
        with st.container():
            # Stream the LLM response.
            response = st.write_stream(response_gen)

            # Add messages to chat history.
            st.session_state.messages.append(
                {"role": "user", "content": question})
            st.session_state.messages.append(
                {"role": "assistant", "content": response})

            # Other stuff.
            show_feedback_controls(len(st.session_state.messages) - 1)
            send_telemetry(question=question, response=response)
