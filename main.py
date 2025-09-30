import os
import json
import chromadb
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import api_key
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import google.generativeai as genai


load_dotenv() 


api_key = os.getenv("GOOGLE_API_KEY")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
chroma_host = os.getenv("CHROMA_HOST")
chroma_port = os.getenv("CHROMA_PORT")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-pro-latest")

DB_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
DB_ENGINE = create_engine(DB_URL)

CHROMA_CLIENT = chromadb.HttpClient(host=chroma_host, port=int(chroma_port))
CHROMA_COLLECTION = CHROMA_CLIENT.get_collection(name="ocean_context")

app = FastAPI()

origins = ["*"] 

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

POSTGRES_SCHEMA = """
Table Name: argo_profiles
Columns:
id (SERIAL),
latitude (FLOAT),
longitude (FLOAT),
timestamp (DATETIME),
platform_id (INTEGER),
cycle_number (INTEGER),
pressure (FLOAT),
temperature (FLOAT),
salinity (FLOAT)
"""

VECTOR_DB_SCHEMA = """
A collection of documents containing contextual summaries of ARGO float
journeys and oceanographic regions. Use this to find relevant platform_ids
or background information.
"""



PLANNING_PROMPT_TEMPLATE = """
You are a world-class oceanographer AI assistant. Your goal is to help users analyze ARGO float data.

You have access to two tools: a PostgreSQL database and a Vector Database.

Tool 1: PostgreSQL Database
Schema:
{postgres_schema}
Use this for precise queries on numerical data like temperature, salinity, pressure, and location.

Tool 2: Vector Database
Schema:
{vector_db_schema}
Use this to find relevant float platform_ids or contextual information based on semantic user queries
(e.g., "floats in the Arabian Sea", "floats with anomalies").

User's Question: "{user_query}"

Based on the user's question, create a plan. Decide which tools to use.

Respond with a single JSON object containing a list of queries to execute.
The JSON object should have one key: "queries".
"queries" is a list of objects, where each object has:

"tool" ('postgres' or 'vector')

"query" (the SQL query or the text to search in the vector DB).

Your Plan:
"""

SYNTHESIS_PROMPT_TEMPLATE = """
You are a helpful oceanographer AI assistant. You have been provided with data retrieved
from a database based on a user's question.

Original User Question: "{user_query}"

Retrieved Data:
```json
{retrieved_data}  
```
Your task is to:

Analyze the provided data.

Write a concise, one-paragraph text insight that answers the user's original question.

Do not mention the database or the data structure. Just state the oceanographic insight.

Insight:
"""
def clean_null_bytes(text: str) -> str:
    """Remove null byte characters from the string."""
    return text.replace('\x00', '')


class UserRequest(BaseModel):
    query: str

@app.get("/trajectories")
async def get_trajectories():
    """
    Retrieves the ordered trajectory for every float in the database.
    """
    try:
        query = text("""
            SELECT 
                platform_id, 
                latitude, 
                longitude 
            FROM 
                argo_profiles 
            ORDER BY 
                platform_id, timestamp ASC;
        """)
        
        with DB_ENGINE.connect() as connection:
            df = pd.read_sql(query, connection)

        trajectories = {}
        for platform_id, group in df.groupby('platform_id'):
            trajectories[str(platform_id)] = group[['latitude', 'longitude']].values.tolist()
            
        return trajectories
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_query(request: UserRequest):
    try:
        planning_prompt = PLANNING_PROMPT_TEMPLATE.format(
            postgres_schema=POSTGRES_SCHEMA,
            vector_db_schema=VECTOR_DB_SCHEMA,
            user_query=request.query
        )
        plan_response = model.generate_content(planning_prompt)

        plan_response_text = clean_null_bytes(plan_response.text.strip())

        try:
            plan = json.loads(plan_response_text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="LLM did not return valid JSON plan.")

        retrieved_data = {}
        data_for_frontend = {}

        for q in plan["queries"]:
            if q["tool"] == "postgres":
                with DB_ENGINE.connect() as connection:
                    df = pd.read_sql(text(q["query"]), connection)
                    data_for_frontend[f"sql_result_{len(data_for_frontend)}"] = df.to_dict(orient="records")

            elif q["tool"] == "vector":
                results = CHROMA_COLLECTION.query(query_texts=[q["query"]], n_results=2)
                retrieved_data[f"vector_result_{len(retrieved_data)}"] = results["documents"]

        retrieved_data["structured_data"] = data_for_frontend

        synthesis_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
            user_query=request.query,
            retrieved_data=json.dumps(retrieved_data, indent=2, default=str)
        )

        insight_response = model.generate_content(synthesis_prompt)

        insight_response_text = clean_null_bytes(insight_response.text.strip())

        final_response = {
            "insight_text": insight_response_text,
            "data_for_charts": data_for_frontend
        }
        return final_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
