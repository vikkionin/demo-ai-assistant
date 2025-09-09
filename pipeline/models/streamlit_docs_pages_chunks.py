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
        post_hook="ALTER CORTEX SEARCH SERVICE streamlit_docs_pages_search_service REFRESH;",
    )

    url = "https://docs.streamlit.io/llms-full.txt"
    df = session.sql(f"select http_get_or_fail('{url}') as page_text;").to_pandas()
    full_str = df.iat[0, 0]
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
