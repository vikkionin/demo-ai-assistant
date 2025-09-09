# DBT pipelien for the Streamlit AI Assistant demo

### Running from your machine

- Set up your Snowflake account at `~/.dbt/profiles.yml` like this:

    ```yml
    ai_assistant_pipeline:
      outputs:
        dev:
          type: snowflake
          account: YOUR_ACCOUNT_NAME # Change this
          database: ST_ASSISTANT_DEV
          schema: PUBLIC
          user: ST_ASSISTANT_PIPELINE
          password: YOUR_USERS_API_TOKEN # Change this
          role: ST_ASSISTANT_PIPELINE
          warehouse: COMPUTE_WH
          threads: 1
        prod:
          type: snowflake
          account: YOUR_ACCOUNT_NAME # Change this
          database: ST_ASSISTANT
          schema: PUBLIC
          user: ST_ASSISTANT_PIPELINE
          password: YOUR_USERS_API_TOKEN # Change this
          role: ST_ASSISTANT_PIPELINE
          warehouse: COMPUTE_WH
          threads: 1
      target: dev # Pick the database you want to modify.
    ```

- Initialize your Python environment:

    ```sh
    $ uv venv
    $ source .venv/bin/activate
    $ uv sync
    ```

- Run the pipeline inside your Snowflake account:

    ```sh
    $ dbt run
    ```
