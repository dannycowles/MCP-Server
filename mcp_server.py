from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.prompts import base
from pydantic import Field
from dotenv import load_dotenv
import os
import psycopg2
import requests

load_dotenv()

db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


mcp = FastMCP("DocumentMCP", log_level="ERROR")

WEATHER_API_URL = "https://api.weather.gov"

docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}

@mcp.tool(
    name="read_doc_contents",
    description="Read the contents of a document and return it as a string.",
)
async def read_document(
        doc_id: str = Field(description="Id of the document to read"), ctx: Context = None
) -> str:
    if doc_id not in docs:
        raise ValueError(f"Document with id {doc_id} not found")
    await ctx.info(f"Reading content from {doc_id}")
    return docs[doc_id]


@mcp.tool(
    name="edit_document",
    description="Edit a document by replacing a string in the documents content with a new string."
)
def edit_document(
        doc_id: str = Field(description="Id of the document that will be edited"),
        old_str: str = Field(description="The text to replace. Must match exactly, including whitespace."),
        new_str: str = Field(description="The new text to insert in place of the old text.")
):
    if doc_id not in docs:
        raise ValueError(f"Document with id {doc_id} not found")

    docs[doc_id] = docs[doc_id].replace(old_str, new_str)


@mcp.tool(
    name="read_file",
    description="Read the contents of a file and return it as a string.",
)
def read_file(
        file_name: str = Field(description="The name of the file to read.")
) -> str:
    try:
        with open(file_name, "r") as file:
            content = file.read()
            return content
    except FileNotFoundError:
        raise ValueError(f"File {file_name} not found")


@mcp.tool(
    name="edit_file",
    description="Edit a file by appending the provided text to the end of the file"
)
def edit_file(
        file_name: str = Field(description="The name of the file to edit."),
        new_text: str = Field(description="The new text to append to the end of the file.")
):
    with open(file_name, "a") as file:
        file.write(new_text)


@mcp.tool(
    name="read_todos",
    description="Read the contents of the todos database table and return as a list of dictionaries"
)
def read_todos() -> list[dict]:
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM todos")

    todos = []
    for row in cursor.fetchall():
        todos.append({
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "is_completed": row[3],
            "created_at": row[4]
        })

    cursor.close()
    conn.close()
    return todos


@mcp.tool(
    name="add_todo",
    description="Add a new todo item to the database."
)
def add_todo(
        title: str = Field(description="Title of the todo item"),
        description: str | None = Field(default=None, description="Longer description if needed")
):
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (title, description) VALUES (%s, %s)", (title, description))
    conn.commit()
    cursor.close()
    conn.close()


@mcp.tool(
    name="complete_todo",
    description="Mark todo item as completed in the database"
)
def complete_todo(
        title: str = Field(description="Title of the todo item being marked as completed")
):
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET completed = TRUE WHERE title = %s", (title,))
    conn.commit()

    updated_rows = cursor.rowcount
    cursor.close()
    conn.close()

    if updated_rows == 0:
        raise ValueError(f"Todo item with title {title} was not found")


@mcp.tool(
    name="delete_todo",
    description="Deletes a todo item from the database"
)
def delete_todo(
        title: str = Field(description="Title of the todo item being deleted from the database")
):
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE title = %s", (title,))
    conn.commit()

    updated_rows = cursor.rowcount
    cursor.close()
    conn.close()

    if updated_rows == 0:
        raise ValueError(f"Todo item with title {title} was not found")


@mcp.tool(
    name="get_weather_alerts",
    description="Get active weather alerts for a specific US state (e.g. 'CA', 'NY')"
)
def get_weather_alerts(
        state: str = Field(description="State of the weather alerts to get data for")
) -> list[dict]:
    try:
        response = requests.get(f"{WEATHER_API_URL}/alerts/active/area/{state}")
        response.raise_for_status()

        features = response.json()["features"]
        alerts = [format_weather_alert(feature) for feature in features]
        return alerts
    except Exception as e:
        raise ValueError(f"Error fetching weather alerts for {state}: {str(e)}")


def format_weather_alert(feature: dict):
    alert_properties = feature.get("properties")
    return {
        "Event": alert_properties.get("event", "Unknown"),
        "Area": alert_properties.get("areaDesc", "Unknown"),
        "Severity": alert_properties.get("severity", "Unknown"),
        "Description": alert_properties.get("description", "Unknown"),
        "Instruction": alert_properties.get("instruction", "Unknown")
    }


@mcp.resource(
    "docs://documents",
    mime_type="application/json"
)
def list_docs() -> list[str]:
    return list(docs.keys())


@mcp.resource(
    "docs://documents/{doc_id}",
    mime_type="text/plain"
)
def fetch_doc(doc_id: str) -> str:
    if doc_id not in docs:
        raise ValueError(f"Document with id {doc_id} not found")
    return docs[doc_id]


@mcp.prompt(
    name="format",
    description="Rewrites the contents of the document in Markdown format."
)
def format_document(
        doc_id: str = Field(description="Id of the document to format.")
) -> list[base.Message]:
    prompt = f"""
    Your goal is to reformat a document to be written with markdown syntax.
    
    The id of the document you need to reformat is:
    <document_id>
    {doc_id}
    </document_id>
    
    Add in headers, bullet points, tables, etc as necessary. Feel free to add in structure.
    Use the 'edit_document' tool to edit the document. After the document has been reformatted...
"""
    return [
        base.UserMessage(prompt)
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
