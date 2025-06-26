# langgraph_agent_system.py

from typing import Any, Dict, Callable, List, Optional
from dataclasses import dataclass, field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import JsonOutputKeyToolsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import uuid

# === Tool Registry Manager ===
class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}

    def register(self, name: str, tool_func: Callable):
        self.tools[name] = tool_func

    def call(self, name: str, **kwargs):
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found.")
        return self.tools[name](**kwargs)

    def list_tools(self):
        return list(self.tools.keys())

# Global registry instance
TOOL_REGISTRY = ToolRegistry()

# === Dummy Tool Implementations ===
def knowledge_base_search_tool(query: str) -> str:
    return f"🔍 Searched KB for: {query}"

def document_search_tool(query: str) -> str:
    return f"📄 Document match for: {query}"

def code_search_tool(query: str) -> str:
    return f"💻 Code matched for: {query}"

# Register tools
TOOL_REGISTRY.register("knowledge_base_search", knowledge_base_search_tool)
TOOL_REGISTRY.register("document_search", document_search_tool)
TOOL_REGISTRY.register("code_search", code_search_tool)

# === Agent State ===
@dataclass
class AgentState:
    messages: List[Any] = field(default_factory=list)
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    retry_count: int = 0

# === LLM Agent ===
llm = ChatOpenAI(model="gpt-4", temperature=0)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a smart agent. Choose tools and arguments wisely."),
    MessagesPlaceholder(variable_name="messages"),
])
agent_runnable: Runnable = prompt | llm | JsonOutputKeyToolsParser()

def agent_node(state: AgentState) -> AgentState:
    output = agent_runnable.invoke({"messages": state.messages})
    state.tool_name = output["tool"]
    state.tool_args = output.get("tool_input", {})
    return state

# === Tool Node ===
def tool_node(state: AgentState) -> AgentState:
    try:
        output = TOOL_REGISTRY.call(state.tool_name, **(state.tool_args or {}))
        state.tool_output = output
        state.retry_count = 0
    except Exception as e:
        state.tool_output = f"❌ Tool Error: {str(e)}"
        state.retry_count += 1
    return state

# === Retry/Refinement Node ===
def refine_node(state: AgentState) -> AgentState:
    if not state.tool_output or "❌" in str(state.tool_output):
        if state.retry_count >= 2:
            state.messages.append(AIMessage(content="Giving up after 2 retries."))
            return state
        refine_prompt = f"Refine the previous tool call for error: {state.tool_output}"
        state.messages.append(AIMessage(content=refine_prompt))
        return agent_node(state)  # Rerun agent to refine
    return state

# === Response Node ===
def response_node(state: AgentState) -> AgentState:
    state.messages.append(ToolMessage(tool_call_id=str(uuid.uuid4()), content=str(state.tool_output)))
    return state

# === LangGraph ===
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tool", tool_node)
graph.add_node("refine", refine_node)
graph.add_node("respond", response_node)

# Edges
graph.set_entry_point("agent")
graph.add_edge("agent", "tool")
graph.add_edge("tool", "refine")
graph.add_edge("refine", "respond")
graph.add_edge("respond", END)

# Build the graph
agent_executor = graph.compile()

# === Test Run ===
if __name__ == "__main__":
    init_state = AgentState(messages=[HumanMessage(content="Find related product to PAN update bug.")])
    final_state = agent_executor.invoke(init_state)
    print("\n--- FINAL TOOL OUTPUT ---")
    print(final_state.tool_output)









Tools

from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import psycopg2
import numpy as np
from psycopg2.extras import Json

# Initialize embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# PostgreSQL connection settings (adjust as needed)
conn = psycopg2.connect(
    dbname="your_db",
    user="your_user",
    password="your_pass",
    host="localhost",
    port="5432"
)

class ToolInput(BaseModel):
    query: str

class ToolResult(BaseModel):
    result: str
    meta: Optional[Dict[str, Any]] = None

# Helper: Query top-k vector matches
def search_pgvector(table: str, vector_col: str, text_col: str, embedding: np.ndarray, k: int = 5):
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT {text_col}, 1 - ({vector_col} <#> %s::vector) as similarity
            FROM {table}
            ORDER BY {vector_col} <#> %s::vector
            LIMIT %s;
        """, (embedding.tolist(), embedding.tolist(), k))
        rows = cur.fetchall()
        return [row[0] for row in rows]

# --- Tool: Knowledge Base Search ---
def knowledge_base_search(input: ToolInput) -> ToolResult:
    embedding = embedding_model.encode(input.query)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT kb.name, kb.description, kb.id
            FROM knowledge_bases kb
            JOIN document_chunks dc ON dc.document_id IN (
                SELECT id FROM documents d
                WHERE d.repository_id IN (
                    SELECT id FROM repositories r WHERE r.knowledge_base_id = kb.id
                )
            )
            WHERE kb.type = 'Product'
            LIMIT 20; -- limit initial scan
        """)
        kbs = cur.fetchall()
    best_match = None
    best_score = -1
    for name, desc, kb_id in kbs:
        kb_embed = embedding_model.encode(desc or name)
        score = np.dot(kb_embed, embedding)
        if score > best_score:
            best_score = score
            best_match = (name, kb_id)
    return ToolResult(result=best_match[0], meta={"kb_id": str(best_match[1]), "score": best_score})

# --- Tool: Document Search ---
def document_search(input: ToolInput, kb_id: UUID) -> ToolResult:
    embedding = embedding_model.encode(input.query)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT dc.chunk_text
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            JOIN repositories r ON d.repository_id = r.id
            WHERE r.knowledge_base_id = %s
        """, (str(kb_id),))
        chunks = cur.fetchall()
    ranked = sorted(((chunk[0], np.dot(embedding_model.encode(chunk[0]), embedding)) for chunk in chunks), key=lambda x: -x[1])
    top_chunks = [text for text, _ in ranked[:5]]
    return ToolResult(result="\n---\n".join(top_chunks))

# --- Tool: Code Search ---
def code_search(input: ToolInput, kb_id: UUID) -> ToolResult:
    embedding = embedding_model.encode(input.query)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cc.content
            FROM code_chunks cc
            JOIN repositories r ON cc.repository_id = r.id
            WHERE r.knowledge_base_id = %s
        """, (str(kb_id),))
        chunks = cur.fetchall()
    ranked = sorted(((chunk[0], np.dot(embedding_model.encode(chunk[0]), embedding)) for chunk in chunks), key=lambda x: -x[1])
    top_chunks = [text for text, _ in ranked[:5]]
    return ToolResult(result="\n---\n".join(top_chunks))

# Optional: Categorize ticket (bug, enhancement, etc.) using LLM
from openai import OpenAI
openai_client = OpenAI(api_key="sk-...")  # Replace with your key

def classify_issue(text: str) -> str:
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Classify the issue as Bug, Data Correction, or Feature Enhancement."},
            {"role": "user", "content": text}
        ]
    )
    return completion.choices[0].message.content.strip()












