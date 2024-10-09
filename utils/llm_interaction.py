import os
from dotenv import load_dotenv
import requests
from config import *


def get_image_explanation(base64_image):
    """Get image explanation from OpenAI API."""
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that responds in Markdown."},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "Explain the content of this image in a single, coherent paragraph. The explanation should be concise and semantically meaningful."
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

def summarize_page(page_text, previous_summary, page_number):
    """Summarize a single page's text using LLM."""
    prompt_message = (
        f"Summarize the following page (Page {page_number}) with context from the previous summary.\n\n"
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
                {"role": "system", "content": "You are an assistant that summarizes text with context."},
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
    
def ask_question(documents, question, chat_history):
    """Answer a question based on the summarized content of multiple PDFs and chat history."""
    combined_content = ""
    
    for doc_name, doc_data in documents.items():
        for page in doc_data["pages"]:
            # Combine text summaries and image analysis
            page_summary = page['text_summary']
            if page["image_analysis"]:
                image_explanation = "\n".join(
                    f"Page {img['page_number']}: {img['explanation']}" for img in page["image_analysis"]
                )
            else:
                image_explanation = "No image analysis."
            
            combined_content += f"Page {page['page_number']}\nSummary: {page_summary}\nImage Analysis: {image_explanation}\n\n"

    # Format the chat history into a conversation format
    conversation_history = ""
    for chat in chat_history:
        user_message = f"User: {chat['question']}\n"
        assistant_response = f"Assistant: {chat['answer']}\n"
        conversation_history += user_message + assistant_response

    # Use the combined content for LLM prompt
    prompt_message = (
        f"Now, using the following document analysis as context, answer the question.\n\n"
        f"Context:\n{combined_content}\n"
        f"Question: {question}"
        f"Previous responses over the current chat session:{conversation_history}\n"
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
                {"role": "system", "content": "You are an assistant that answers questions based on provided knowledge base."},
                {"role": "user", "content": prompt_message}
            ],
            "temperature": 0.0
        }
    )

    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")