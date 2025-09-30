import os
import pandas as pd
import psycopg2
import chromadb
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from dotenv import load_dotenv
import json
import math

# ==============================================================================
# 1. SETUP AND CONFIGURATION
# ==============================================================================

print("🚀 Starting ARGO Data Processing and Indexing Pipeline...")

# Load environment variables
load_dotenv()

# Configure the Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Database connection details
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = "localhost"

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST)

# ==============================================================================
# 2. THE REVISED GEMINI PROMPT
# ==============================================================================

def get_gemini_prompt(record_json: str):
    """
    Creates the revised, detailed prompt for Gemini to generate structured
    oceanographic documentation.
    """
    return f"""
    You are an expert oceanographer AI assistant. Your task is to create a concise, human-readable summary and structured documentation for a single ARGO float based on its raw measurement data.

    Input: A JSON object representing a row of data from the float's profile measurements.

    Instructions:
    Follow this chain of thought to arrive at the final summary:
    1.  **Analyze Trajectory:** Based on the 'region' field, determine the primary ocean basin.
    2.  **Analyze Time Range:** Identify the start and end dates of the measurements from the 'profile_date'.
    3.  **Identify Key Oceanographic Features:**
        * Find the maximum temperature and minimum salinity values if available.
        * Note any significant anomalies or trends, such as a high chlorophyll value suggesting a bloom.
    4.  **Synthesize Summary:** Combine your findings into a concise, 3–5 sentence paragraph. Convert all data into readable text. Do not include raw JSON or tables.

    Output Format: Provide the final answer in a single, clean JSON object. Do not add any text before or after the JSON.

    ```json
    {{
      "platform_id": <platform_id>,
      "region": "<primary region or ocean basin>",
      "time_range": "<start date (YYYY-MM-DD) to end date (YYYY-MM-DD)>",
      "summary": "<human-readable text summary combining trajectory, time, and key findings>",
      "oceanographic_features": {{
        "max_temperature_celsius": <value or null>,
        "min_salinity_psu": <value or null>,
        "significant_anomalies": "<brief note on any anomalies or 'normal conditions'>"
      }}
    }}
    ```
    
    Here is the data:
    {record_json}
    """

# ==============================================================================
# 3. DATA FETCHING, DOCUMENTATION, AND INDEXING (CORRECTED FUNCTION)
# ==============================================================================

def fetch_process_and_index_data(table_name: str, batch_size: int = 100, page_number: int = 1):
    """
    Fetches a specific batch/page of data from PostgreSQL, processes it, and indexes it.
    """
    print(f"🚀 Processing Page {page_number} (Records { (page_number-1)*batch_size + 1 } to { page_number*batch_size })...")
    
    offset = (page_number - 1) * batch_size
    
    # --- Step 1: Fetch Data from PostgreSQL ---
    try:
        with get_db_connection() as conn:
            query = f"SELECT * FROM {table_name} ORDER BY profile_date DESC LIMIT %s OFFSET %s;"
            df = pd.read_sql_query(query, conn, params=(batch_size, offset))
        print(f"✅ Successfully fetched {len(df)} records.")
        if len(df) == 0:
            print("No more records to process for this batch.")
            return
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        raise # Raise the exception to be caught by the main loop

    # --- Step 2: Generate Documentation with Gemini ---
    print("🤖 Generating advanced oceanographic documentation with Gemini...")
    summaries_for_chroma = []
    
    for index, row in df.iterrows():
        record_json = row.to_json(default_handler=str)
        prompt = get_gemini_prompt(record_json)
        
        try:
            response = gemini_model.generate_content(prompt)
            cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
            gemini_output = json.loads(cleaned_response)
            summaries_for_chroma.append(gemini_output.get("summary", "Summary not available."))
        except Exception as e:
            print(f"⚠️ Warning: Could not process Gemini response for record {index}. Error: {e}")
            summaries_for_chroma.append(f"Documentation failed for record {index}.")

    # --- Step 3: Index the Summaries into ChromaDB ---
    print("⚡️ Creating embeddings and indexing into ChromaDB...")
    
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    chroma_client = chromadb.PersistentClient(path="./argo_chroma_db_final")
    collection = chroma_client.get_or_create_collection("argo_ocean_docs")

    documents = summaries_for_chroma
    ids = df['id'].astype(str).tolist() if 'id' in df.columns else [str(i) for i in df.index]

    embeddings = embedding_model.encode(documents)
    collection.add(
        embeddings=embeddings.tolist(),
        documents=documents,
        ids=ids,
        metadatas=df.to_dict('records')
    )
    
    print(f"✅ Successfully indexed {collection.count()} documents into ChromaDB.")

# ==============================================================================
# 4. MAIN EXECUTION (FAULT-TOLERANT & AUTOMATED)
# ==============================================================================

if __name__ == "__main__":
    
    TABLE_TO_PROCESS = "argo_profiles"
    BATCH_SIZE = 100
    PROGRESS_FILE = "processing_progress.log"

    def get_start_page():
        if not os.path.exists(PROGRESS_FILE):
            return 1
        try:
            with open(PROGRESS_FILE, 'r') as f:
                last_completed_page = int(f.read().strip())
                print(f"Resuming from page {last_completed_page + 1}.")
                return last_completed_page + 1
        except (ValueError, FileNotFoundError):
            return 1

    def log_completed_page(page_number):
        with open(PROGRESS_FILE, 'w') as f:
            f.write(str(page_number))

    total_records = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {TABLE_TO_PROCESS};")
            total_records = cur.fetchone()[0]
            
    if total_records == 0:
        print("Table is empty. Nothing to process.")
    else:
        total_pages = math.ceil(total_records / BATCH_SIZE)
        start_page = get_start_page()
        
        print(f"Found {total_records} records. Processing from page {start_page} to {total_pages}.")
        
        for page in range(start_page, total_pages + 1):
            try:
                fetch_process_and_index_data(
                    table_name=TABLE_TO_PROCESS, 
                    batch_size=BATCH_SIZE, 
                    page_number=page
                )
                log_completed_page(page)
                print(f"✅ Successfully completed and logged page {page}.")
            except Exception as e:
                print(f"❌ CRITICAL ERROR on page {page}: {e}")
                print("Stopping script. You can restart it to resume from this page.")
                break
            
        if get_start_page() > total_pages:
            print("\n🎉 All batches have been processed successfully!")