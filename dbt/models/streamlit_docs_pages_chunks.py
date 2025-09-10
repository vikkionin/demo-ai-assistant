import re

from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd

PAGE_SEP_RE = re.compile("^---$", flags=re.MULTILINE)
URL_RE = re.compile("^Source: (.*)$", flags=re.MULTILINE)


def model(dbt, session):
    dbt.config(
        materialized="table",
        packages=[
            "langchain",
            "pandas",
        ],
        # Recreate the Cortex search service every time because we're deleting / recreating
        # the table it depends on.
        post_hook="""
            create or replace cortex search service streamlit_docs_pages_search_service
                on page_chunk
                attributes page_url
                warehouse = compute_wh
                target_lag = '10 minutes'
                initialize = on_create
                as (
                    select *
                    from streamlit_docs_pages_chunks
                );
            grant usage on
                cortex search service
                streamlit_docs_pages_search_service
                to st_assistant_user;
        """,
    )

    url = "https://docs.streamlit.io/llms-full.txt"
    df = session.sql(f"select * from table(http_get_or_fail('{url}'));").to_pandas()
    full_str = df["TEXT"].str.cat(sep="\n")
    page_strs = PAGE_SEP_RE.split(full_str)

    text_splitter = RecursiveCharacterTextSplitter()
    page_table_rows = []

    for page_str in page_strs:
        url = None

        for match in URL_RE.finditer(page_str):
            if match.lastindex == 1:
                url = match[1]
                break

        chunks = text_splitter.split_text(page_str)

        for chunk in chunks:
            page_table_rows.append(
                dict(
                    PAGE_URL=url,
                    PAGE_CHUNK=chunk,
                )
            )

    return pd.DataFrame(page_table_rows)
