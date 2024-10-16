import os
from dotenv import load_dotenv
import requests
from utils.config import azure_endpoint, api_key, api_version, model
import logging
import time
import requests
import random

# Set up logging
logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")

def get_headers():
    """Generate common headers for the API requests."""
    return {
        "Content-Type": "application/json",
        "api-key": api_key
    }



def get_image_explanation(base64_image, retries=5, initial_delay=2):
    """Get image explanation from OpenAI API with exponential backoff."""
    headers = get_headers()
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that responds in Markdown."},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "Explain the contents and figures or tables if present of this image of a document page. The explanation should be concise and semantically meaningful. Do not make assumptions about the specification and be accurate in your explanation."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                }
            ]}
        ],
        "temperature": 0.0
    }

    url = f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"

    # Exponential backoff retry mechanism
    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)  # Adjusted timeout
            response.raise_for_status()  # Raise HTTPError for bad responses
            
            result = response.json()
            # Extract token usage from the response
            token_usage = result.get('usage', {})
            input_tokens = token_usage.get('prompt_tokens', 'N/A')
            output_tokens = token_usage.get('completion_tokens', 'N/A')
            total_tokens = token_usage.get('total_tokens', 'N/A')

            # Log token usage
            logging.info(f"Image explanation: Input tokens = {input_tokens}, Output tokens = {output_tokens}, Total tokens = {total_tokens}")

            return result.get('choices', [{}])[0].get('message', {}).get('content', "No explanation provided.")

        except requests.exceptions.Timeout as e:
            if attempt < retries - 1:
                wait_time = initial_delay * (2 ** attempt)  # Exponential backoff
                logging.warning(f"Timeout error. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{retries})")
                time.sleep(wait_time)
            else:
                logging.error(f"Request failed after {retries} attempts due to timeout: {e}")
                return f"Error: Request timed out after {retries} retries."

        except requests.exceptions.RequestException as e:
            logging.error(f"Error requesting image explanation: {e}")
            return f"Error: Unable to fetch image explanation due to network issues or API error."

    return "Error: Max retries reached without success."


def generate_system_prompt(document_content):
    """
    Generate a system prompt based on the expertise, tone, and voice needed 
    to summarize the document content.
    """
    headers = get_headers()
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that serves the task given."},
            {"role": "user", "content":
             f"""You are provided with a document. Based on its content, extract and identify the following details:
            Document_content: {document_content}

            1. **Domain**: Identify the specific domain or field of expertise the document is focused on. Examples include technology, finance, healthcare, law, etc.
            2. **Subject Matter**: Determine the main topic or focus of the document. This could be a detailed concept, theory, or subject within the domain.
            3. **Experience**: Based on the content, infer the level of experience required to understand or analyze the document (e.g., novice, intermediate, expert).
            4. **Expertise**: Identify any specialized knowledge, skills, or proficiency in a particular area that is necessary to evaluate the content.
            5. **Educational Qualifications**: Infer the level of education or qualifications expected of someone who would need to review or write the document (e.g., PhD, Master's, Bachelor's, or certification in a field).
            6. **Style**: Describe the writing style of the document. Is it formal, technical, conversational, academic, or instructional?
            7. **Tone**: Identify the tone used in the document. For example, is it neutral, authoritative, persuasive, or informative?
            8. **Voice**: Analyze whether the voice is active, passive, first-person, third-person, or impersonal, and whether it's personal or objective.

            After extracting this information, use it to fill in the following template:
    
            ---

            You are now assuming a persona based on the content of the provided document. Your persona should reflect the <domain> and <subject matter> of the content, with the requisite <experience>, <expertise>, and <educational qualifications> to analyze the document effectively. Additionally, you should adopt the <style>, <tone> and <voice> present in the document. Your expertise includes:
    
            <Domain>-Specific Expertise:
            - In-depth knowledge and experience relevant to the <subject matter> of the document.
            - Familiarity with the key concepts, terminology, and practices within the <domain>.
            
            Analytical Proficiency:
            - Skilled in interpreting and evaluating the content, structure, and purpose of the document.
            - Ability to assess the accuracy, clarity, and completeness of the information presented.
    
            Style, Tone, and Voice Adaptation:
            - Adopt the writing <style>, <tone>, and <voice> used in the document to ensure consistency and coherence.
            - Maintain the level of formality, technicality, or informality as appropriate to the document’s context.
            
            Your analysis should include:
            - A thorough evaluation of the content, ensuring it aligns with <domain>-specific standards and practices.
            - An assessment of the clarity and precision of the information and any accompanying diagrams or illustrations.
            - Feedback on the strengths and potential areas for improvement in the document.
            - A determination of whether the document meets its intended purpose and audience requirements.
            - Proposals for any necessary amendments or enhancements to improve the document’s effectiveness and accuracy.
        
            ---

            Generate a response filling the template with appropriate details based on the content of the document and return the filled in template as response."""}
        ],
        "temperature": 0.5  # Adjust as needed to generate creative but relevant system prompts
    }

    try:
        response = requests.post(
            f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
            headers=headers,
            json=data,
            timeout=20
        )
        response.raise_for_status()
        
        # Extract token usage from the response
        token_usage = response.json().get('usage', {})
        input_tokens = token_usage.get('prompt_tokens', 'N/A')
        output_tokens = token_usage.get('completion_tokens', 'N/A')
        total_tokens = token_usage.get('total_tokens', 'N/A')

        # Log token usage
        logging.info(f"Generate system prompt: Input tokens = {input_tokens}, Output tokens = {output_tokens}, Total tokens = {total_tokens}")

        prompt_response = response.json().get('choices', [{}])[0].get('message', {}).get('content', "")
        return prompt_response.strip()

    except requests.exceptions.RequestException as e:
        logging.error(f"Error generating system prompt: {e}")
        return f"Error: Unable to generate system prompt due to network issues or API error."


def summarize_page(page_text, previous_summary, page_number, system_prompt, max_retries=5, base_delay=1, max_delay=32):
    """
    Summarize a single page's text using LLM, and generate a system prompt based on the document content.
    Implements exponential backoff with jitter to handle timeout errors.
    """
    headers = get_headers()
    
    # Generate the system prompt based on the document content
    prompt_message = (
        f"Please rewrite the following page content from (Page {page_number}) along with context from the previous page summary "
        f"to make them concise and well-structured. Maintain proper listing and referencing of the contents if present. "
        f"Do not add any new information or make assumptions. Keep the meaning accurate and the language clear.\n\n"
        f"Previous page summary: {previous_summary}\n\n"
        f"Current page content:\n{page_text}\n"
    )

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_message}
        ],
        "temperature": 0.0
    }
    
    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.post(
                f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
                headers=headers,
                json=data,
                timeout=50
            )
            response.raise_for_status()

            # Extract token usage from the response
            token_usage = response.json().get('usage', {})
            input_tokens = token_usage.get('prompt_tokens', 'N/A')
            output_tokens = token_usage.get('completion_tokens', 'N/A')
            total_tokens = token_usage.get('total_tokens', 'N/A')

            # Log token usage
            logging.info(f"Summarize page {page_number}: Input tokens = {input_tokens}, Output tokens = {output_tokens}, Total tokens = {total_tokens}")

            return response.json().get('choices', [{}])[0].get('message', {}).get('content', "No summary provided.").strip()
        
        except requests.exceptions.RequestException as e:
            attempt += 1
            if attempt >= max_retries:
                logging.error(f"Error summarizing page {page_number}: {e}")
                return f"Error: Unable to summarize page {page_number} due to network issues or API error."

            # Calculate exponential backoff with jitter
            delay = min(max_delay, base_delay * (2 ** attempt))  # Exponential backoff
            jitter = random.uniform(0, delay)  # Add jitter for randomness
            logging.warning(f"Retrying in {jitter:.2f} seconds (attempt {attempt}) due to error: {e}")
            time.sleep(jitter)

def ask_question(documents, question, chat_history):
    """Answer a question based on the full text, summarized content of multiple PDFs, and chat history."""
    combined_content = ""

    # Combine document full texts, summaries, and image analyses with document names
    for doc_name, doc_data in documents.items():
        combined_content += f"\nDocument: {doc_name}\n"  # Add document name for clarity
        for page in doc_data["pages"]:
            page_summary = page['text_summary']
            page_full_text = page.get('full_text', 'No text available')  # Include full text

            image_explanation = "\n".join(
                f"Page {img['page_number']}: {img['explanation']}" for img in page["image_analysis"]
            ) if page["image_analysis"] else "No image analysis."

            combined_content += (
                f"Page {page['page_number']}\n"
                f"Full Text: {page_full_text}\n"
                f"Summary: {page_summary}\n"
                f"Image Analysis: {image_explanation}\n\n"
            )

    # Format the chat history into a conversation format
    conversation_history = "".join(
        f"User: {chat['question']}\nAssistant: {chat['answer']}\n" for chat in chat_history
    )

    # Prepare the prompt message with document name references
    prompt_message = (
        f"""
    You are given the following content from multiple documents:

    ---
    {combined_content}
    ---
    Previous responses over the current chat session: {conversation_history}

    Answer the following question based **strictly and only** on the factual information provided in the content above. 
    Carefully verify all details from the content and do not generate any information that is not explicitly mentioned in it.
    If the answer cannot be determined from the content, explicitly state that the information is not available.
    Ensure the response is clearly formatted for readability.

    Include references to the document name and page number(s) where the information was found.

    Question: {question}
    """
    )

    headers = get_headers()

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an assistant that answers questions based only on provided knowledge base."},
            {"role": "user", "content": prompt_message}
        ],
        "temperature": 0.0
    }

    try:
        response = requests.post(
            f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
            headers=headers,
            json=data,
            timeout=60  # Add timeout for API request
        )
        response.raise_for_status()  # Raise HTTPError for bad responses

        # Extract token usage from the response
        token_usage = response.json().get('usage', {})
        input_tokens = token_usage.get('prompt_tokens', 'N/A')
        output_tokens = token_usage.get('completion_tokens', 'N/A')
        total_tokens = token_usage.get('total_tokens', 'N/A')

        # Log token usage
        logging.info(f"Ask question: Input tokens = {input_tokens}, Output tokens = {output_tokens}, Total tokens = {total_tokens}")

        return response.json().get('choices', [{}])[0].get('message', {}).get('content', "No answer provided.").strip()

    except requests.exceptions.RequestException as e:
        logging.error(f"Error answering question '{question}': {e}")
        raise Exception(f"Unable to answer the question due to network issues or API error.")
