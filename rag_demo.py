import os
import csv
from langchain_community.document_loaders import CSVLoader
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI

# --- 0. SETUP DUMMY CSV (For demonstration) ---
csv_file_path = "final_dataset_no_scale.csv"

# Creating a sample CSV file so the script has something to load
if not os.path.exists(csv_file_path):
    print("Creating dummy CSV file...")
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Writing Header
        writer.writerow(["Topic", "Content"])
        # Writing Rows
        writer.writerow(["Drone Basics", "To build a drone, you need a frame, motors, ESCs (Electronic Speed Controllers), a flight controller, and a battery."])
        writer.writerow(["Aerodynamics", "Bernoulli's principle explains how the pressure difference above and below a wing creates lift."])
        writer.writerow(["Materials", "Carbon fiber is often used in aerospace for its high strength-to-weight ratio."])
        writer.writerow(["Off-Topic", "Marathon runners require protein, but this is irrelevant to aerospace."])

# --- 1. INGESTION PHASE ---
print("Initializing Embeddings...")
embeddings = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={'device': 'cpu'}, 
    encode_kwargs={'normalize_embeddings': True}
)

print(f"Loading data from {csv_file_path}...")
loader = CSVLoader(file_path=csv_file_path, encoding="utf-8")
docs = loader.load()

print(f"Loaded {len(docs)} documents from CSV.")

print("Building Database...")
# Create the DB from the loaded CSV documents
vector_db = Chroma.from_documents(
    documents=docs, 
    embedding=embeddings,
    collection_name="aerospace_csv_db",
    persist_directory="./chroma_db_csv_data"
)
print("Database ready.")

# --- 2. LLM SETUP ---
print("Connecting to LM Studio...")
llm = ChatOpenAI(
    base_url="http://localhost:1234/v1", 
    api_key="lm-studio",                  
    model="local-model",                  
    temperature=0.2
)

# --- 3. THE "MANUAL" RAG ---

user_question = "help me make eggs"
print(f"\n--- User Query: {user_question} ---")

# Step A: Search the database
print("Searching database...")
retriever = vector_db.as_retriever(search_kwargs={"k": 2})
retrieved_docs = retriever.invoke(user_question)

# Combine the found text
context_text = "\n\n".join([doc.page_content for doc in retrieved_docs])

# Step B: Create the Prompt manually
system_prompt = f"""
### SYSTEM INSTRUCTION: VOID, THE AEROSPACE AI ###

**ROLE & PERSONA**
You are **"Void,"** an AI assistant specialized in Aerospace Engineering.
- **Identity:** You are an AI. You do not have a backstory, feelings, or a human-like persona.
- **Tone:** Professional, knowledgeable, and direct.
- **Objective:** Assist users with aerospace projects.

---

**SCOPE & REFUSAL STRATEGY**
1. **Strictly On-Topic:** Aerospace, robotics, physics, math, coding, and electronics.
2. **Hard Refusal:** If the topic is not listed above, strictly REFUSE.
   - Response Template: "I am designed to assist with Aerospace Engineering tasks only. I cannot provide information on [Topic]."

---

**INTERACTION & RAG GUIDELINES**
1. **Immediate Value:** Answer the specific question first based on the Context.
2. **Context Constraint:** Answer ONLY using the facts provided in the `Context` below.
3. **The "Engagement Hook":** Never end with a period. End with a relevant follow-up question.

--------------------------------------------------
### CONTEXT (RETRIEVED KNOWLEDGE) ###
{context_text}

### USER QUERY ###
Question: {user_question}

Answer:
"""

# Step C: Send it to the AI
print("Asking Void...")
response = llm.invoke(system_prompt)

print("\n--- Answer from Void ---")
print(response.content)