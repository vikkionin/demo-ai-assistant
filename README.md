# Streamlit AI assistant &mdash; a documentation chatbot for Streamlit

Ever wanted to chat with the Streamlit documentation? Well, with the power of
[Snowflake Cortex](https://docs.snowflake.com/en/guides-overview-ai-features?utm_source=streamlit&utm_medium=referral&utm_campaign=streamlit-demo-apps&utm_content=streamlit-assistant)
now you can!

You can try out the AI Assistant app below:

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://st-assistant.streamlit.app/)

## Running it yourself

### Snowflake pipeline setup

1. In `Projects`, create a new workspace from this Git repo or copy/paste
   files into your favorite workspace.

1. Double click on `dbt/snowflake_setup.sql` then click ▶️ to run it.

   NOTE: By default, this code sets up the *dev* pipeline.

   To set up the *prod* pipeline, look at the line that says `IMPORTANT`,
   uncomment the appropriate `db_name` variable, and rerun the script.

1. Run the DBT project through the UI to check that it works.

1. If all goes well, you can now deploy and schedule this to rerun every
   month using the Workspaces UI.

### Try it on your machine

1. Get the code:

   ```sh
   $ git clone https://github.com/streamlit/demo-ai-assistant
   ```

1. Start a virtual environment and get the dependencies (requires uv):

   ```sh
   $ uv venv
   $ .venv/bin/activate
   $ uv sync
   ```

1. Start the app:

    ```sh
    $ streamlit run streamlit_app.py
    ```
