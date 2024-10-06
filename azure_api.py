import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from the .env file

azure_endpoint = os.getenv("AZURE_ENDPOINT")
api_key = os.getenv("API_KEY")
api_version = os.getenv("API_VERSION")
model = os.getenv("MODEL")

# Modify get_image_explanation to include a document context for comparative study
def get_image_explanation(base64_image, document_name):
    """Get image explanation from OpenAI API, including document context."""
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": f"You are a helpful assistant that analyzes images for {document_name}."},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": f"Explain the content of this image from the document '{document_name}' in a single, coherent paragraph."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                }
            ]}
        ],
        "temperature": 0.7
    }

    response = requests.post(
        f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
        headers=headers,
        json=data
    )
    if response.status_code == 200:
        explanation = response.json()['choices'][0]['message']['content']
        return explanation
    else:
        return f"Error: {response.status_code}, {response.text}"

# Modify summarize_page to include document context and handle multiple documents
def summarize_page(page_text, previous_summary, page_number, document_name):
    """Summarize a single page's text using LLM, considering document context."""
    prompt_message = (
        f"Summarize the following page from the document '{document_name}' (Page {page_number}) with context from the previous summary.\n\n"
        f"Previous summary: {previous_summary}\n\n"
        f"Text:\n{page_text}\n"
    )

    response = requests.post(
        f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
        headers={
            "Content-Type": "application/json",
            "api-key": api_key
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": f"You are an assistant that summarizes text with context from the document '{document_name}'."},
                {"role": "user", "content": prompt_message}
            ],
            "temperature": 0.0
        }
    )
    
    if response.status_code == 200:
        summary = response.json()['choices'][0]['message']['content'].strip()
        return summary
    else:
        return f"Error: {response.status_code}, {response.text}"

# New function to handle questions based on summaries from multiple documents
def ask_question(document_data, question):
    """Answer user questions based on multiple document summaries."""
    # Combine summaries from all documents into a single context
    combined_summaries = []
    for doc_name, doc_info in document_data.items():
        doc_summaries = "\n".join([page['text_summary'] for page in doc_info['pages']])
        combined_summaries.append(f"Document: {doc_name}\n{doc_summaries}")
    combined_content = "\n\n".join(combined_summaries)

    # Prepare the question prompt
    prompt_message = (
        f"You are an assistant that answers questions based on multiple documents.\n\n"
        f"Combined document summaries:\n{combined_content}\n\n"
        f"Question: {question}\n"
    )

    # Send request to OpenAI API
    response = requests.post(
        f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
        headers={
            "Content-Type": "application/json",
            "api-key": api_key
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an assistant that answers questions about documents."},
                {"role": "user", "content": prompt_message}
            ],
            "temperature": 0.7
        }
    )

    if response.status_code == 200:
        answer = response.json()['choices'][0]['message']['content'].strip()
        return answer
    else:
        return f"Error: {response.status_code}, {response.text}"
