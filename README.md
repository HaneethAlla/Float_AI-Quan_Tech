# Float_AI-Quan_Tech

# Ocean Insight: AI-Powered Argo Explorer 🌊

**A submission for the Smart India Hackathon 2025 by Team Quan-Tech.**

Ocean Insight is an intelligent platform designed to make complex oceanographic data from ARGO floats accessible, understandable, and actionable through the power of generative AI.

---

## 🎯 The Problem

Oceanographic data, while crucial for climate science, maritime industries, and policy-making, is incredibly vast and stored in complex formats like NetCDF. This makes it largely inaccessible to non-expert users such as students, policymakers, or even researchers from different fields. Extracting simple insights requires specialized tools and significant domain expertise.

## ✨ Our Solution

Ocean Insight bridges this gap by providing a seamless, conversational interface to the ARGO dataset. Our platform allows users to ask questions in plain English, which are then translated by a powerful AI engine into precise database queries. The results are delivered back not just as raw data, but as easy-to-understand text summaries and interactive visualizations.

## 🚀 Key Features

* **AI-Powered Chat Assistant:** Ask complex questions in natural language (e.g., "Compare the salinity of float X and Y") and get immediate, accurate answers.
* **Natural Language to SQL:** A sophisticated RAG (Retrieval-Augmented Generation) pipeline that uses a Large Language Model (LLM) to dynamically generate and execute SQL queries.
* **Interactive Data Visualizations:** The AI's response includes auto-generated charts (e.g., Temperature vs. Depth profiles) created with Plotly.js for in-depth analysis.
* **Live Map Trajectories:** An interactive map (powered by Leaflet) that visualizes the real-world paths of all ARGO floats from the database.
* **Polished & Resizable UI:** A clean, modern, and user-friendly interface built with TailwindCSS.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI
* **AI Engine:** Google Gemini (`gemini-pro-latest`)
* **Database:** PostgreSQL, chromadb
* **Frontend:** HTML, CSS, JavaScript, TailwindCSS
* **Charting:** Plotly.js
* **Mapping:** Leaflet.js

## ⚙️ Setup and Installation Guide

Follow these steps to set up and run the project locally.

### Prerequisites
* Python 3.9+
* Git
* PostgreSQL

### 1. Clone the Repository
```bash
git clone [https://github.com/](https://github.com/)[YOUR_USERNAME]/[YOUR_REPO_NAME].git
cd Float_AI-Quan_Tech
```

### 2. Set Up Environment Variables
Copy the example environment file and fill in your own secret keys and database credentials.

```bash
cp .env.example .env
```
Now, open the `.env` file and add your `GOOGLE_API_KEY` and your PostgreSQL `DB_PASSWORD`.

### 3. Install Dependencies
Install all the required Python libraries using pip.

```bash
pip install -r requirements.txt
```

### 4. Set Up the Database
You only need to do this once.
1.  In a PostgreSQL tool like `pgAdmin` or `psql`, create a new, empty database named `ocean_insight`.
2.  in sql using python argo_load.py to injest data from argo database or can use the .nc files in data for testing add them  to postgresql and sql_to_chroma.py file to update chromadb database
3.  Run our ingestion script to populate the database with the sample ARGO data included in this repository.
    ```bash
    python ingest_data.py
    ```

### 5. Run the Application
1.  **Start the Backend:** Run the FastAPI server from your terminal. Keep this terminal window open.
    ```bash
    uvicorn main:app --reload
    ```
2.  **Launch the Frontend:** Open the `index.html` file in your web browser or run live server.

The application should now be fully functional.

---

## 🧑‍💻 Team Members

* A.Haneeth
* Ansh yemul
* Rajan Nayak
* Hruthika K
* K.yaswanth
* Nandhan
