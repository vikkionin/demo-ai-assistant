# DBT pipeline for the Streamlit AI Assistant demo

To set up your Snowflake account, do the following:

1. In `Projects`, create a new workspace from this Git repo or copy/paste
   files into your favorite workspace.

1. Double click on `snowflake_setup.sql` then click ▶️ to run it.

   NOTE: By default, this code sets up the *dev* pipeline.

   To set up the *prod* pipeline, look at the line that says `IMPORTANT`,
   uncomment the appropriate `db_name` variable, and rerun the script.

1. Double click the DBT project file and click ▶️ to run it.
1. If all goes well, you can deploy and schedule this to rerun every
   month using the Workspaces UI.
