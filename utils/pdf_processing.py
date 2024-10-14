import fitz
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.file_conversion import convert_office_to_pdf
from utils.llm_interaction import summarize_page, get_image_explanation, generate_system_prompt
import io
import base64
import logging
from pydantic import BaseModel, Field, ValidationError
from typing import Union
import json

# Set up logging
logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")

class SystemPromptOutput(BaseModel):
    document: str = Field(..., description="The name of the document")
    domain: str = Field(..., description="The domain or field of the document")
    subject: str = Field(..., description="The subject of the document")
    expertise: str = Field(..., description="The expertise level required for understanding the document")
    qualification: str = Field(..., description="The qualification required to understand or summarize the document")
    style: str = Field(..., description="The style of the prompt (e.g., professional, casual)")
    tone: str = Field(..., description="The tone of the summary (e.g., formal, neutral)")
    voice: str = Field(..., description="The voice of the prompt (e.g., first-person, third-person)")

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    return ' '.join(text.split())

def detect_ocr_images_and_vector_graphics_in_pdf(page, ocr_text_threshold=0.4):
    """Detect OCR images or vector graphics on a given PDF page."""
    try:
        images = page.get_images(full=True)
        text_blocks = page.get_text("blocks")
        vector_graphics_detected = bool(page.get_drawings())

        # Calculate text coverage
        page_area = page.rect.width * page.rect.height
        text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
        text_coverage = text_area / page_area if page_area > 0 else 0

        pix = page.get_pixmap()
        img_data = pix.tobytes("png")
        base64_image = base64.b64encode(img_data).decode("utf-8")
        pix = None  # Free up memory for pixmap

        if (images or vector_graphics_detected) and text_coverage < ocr_text_threshold:
            return base64_image  # Return image data if OCR image or vector graphics detected

    except Exception as e:
        logging.error(f"Error detecting OCR images/graphics on page {page.number}: {e}")
    
    return None

def process_page_batch(pdf_document, batch, system_prompt, ocr_text_threshold=0.4):
    """Process a batch of PDF pages and extract summaries, full text, and image analysis."""
    previous_summary = ""
    batch_data = []

    for page_number in batch:
        try:
            page = pdf_document.load_page(page_number)
            text = page.get_text("text").strip()
            preprocessed_text = remove_stopwords_and_blanks(text)

            # Summarize the page
            summary = summarize_page(preprocessed_text, previous_summary, page_number + 1, system_prompt)
            previous_summary = summary

            # Detect images or vector graphics
            image_data = detect_ocr_images_and_vector_graphics_in_pdf(page, ocr_text_threshold)
            image_analysis = []
            if image_data:
                image_explanation = get_image_explanation(image_data)
                image_analysis.append({"page_number": page_number + 1, "explanation": image_explanation})

            # Store the extracted data, including the text
            batch_data.append({
                "page_number": page_number + 1,
                "full_text": text,  # Adding full text to batch data
                "text_summary": summary,  
                "image_analysis": image_analysis
            })

        except Exception as e:
            logging.error(f"Error processing page {page_number + 1}: {e}")
            batch_data.append({
                "page_number": page_number + 1,
                "full_text": "",  # Include empty text in case of an error
                "text_summary": "Error in processing this page",
                "image_analysis": []
            })

    return batch_data

def process_pdf_pages(uploaded_file):
    """Process the PDF pages in batches and extract summaries and image analysis."""
    file_name = uploaded_file.name
    
    try:
        # Check if the uploaded file is a PDF
        if file_name.lower().endswith('.pdf'):
            pdf_stream = io.BytesIO(uploaded_file.read())  # Directly read PDF
        else:
            # Convert Office files to PDF if necessary
            pdf_stream = convert_office_to_pdf(uploaded_file)
        
        # Process the PDF document
        pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
        document_data = {"document_name": file_name, "pages": []}  # Add document_name at the top
        total_pages = len(pdf_document)

        # Prepare document content for system prompt generation
        # Use the first 3 pages for system prompt generation
        document_content = ""
        for page_num in range(min(3, total_pages)):
            page = pdf_document.load_page(page_num)
            document_content += page.get_text("text")
        
        # Generate the system prompt using the modified function
        system_prompt_data = generate_system_prompt(document_content)

        # Ensure the system prompt is valid
        if isinstance(system_prompt_data, dict):  # Check for dictionary type
            # Extract the required fields from the dictionary
            document_name = system_prompt_data.get("document", "example_document")
            domain = system_prompt_data.get("domain", "General")
            subject = system_prompt_data.get("subject", "General topic")
            expertise = system_prompt_data.get("expertise", "General knowledge")
            qualification = system_prompt_data.get("qualification", "No qualification specified")
            style = system_prompt_data.get("style", "Informal")
            tone = system_prompt_data.get("tone", "Neutral")
            voice = system_prompt_data.get("voice", "Neutral")

            # Create the system prompt using the variables
            system_prompt = {
                "role": "system",
                "content": f"You are an expert in {domain} {subject} with an expertise in {expertise} and qualification of {qualification}. "
                           f"Your response should be {style}, {tone}, and in a {voice} voice."
            }
        else:
            logging.error("System prompt data is invalid.")
            system_prompt = {
                "role": "system",
                "content": "Default system prompt. The system prompt could not be generated."
            }  # Fallback in case of failure

        # Batch size of 5 pages
        batch_size = 5
        page_batches = [range(i, min(i + batch_size, total_pages)) for i in range(0, total_pages, batch_size)]
        
        # Use ThreadPoolExecutor to process batches concurrently
        with ThreadPoolExecutor() as executor:
            future_to_batch = {executor.submit(process_page_batch, pdf_document, batch, system_prompt): batch for batch in page_batches}
            for future in as_completed(future_to_batch):
                try:
                    batch_data = future.result()  # Get the result of processed batch
                    document_data["pages"].extend(batch_data)
                except Exception as e:
                    logging.error(f"Error processing batch: {e}")

        # Close the PDF document after processing
        pdf_document.close()

        # Sort pages by page_number to ensure correct order
        document_data["pages"].sort(key=lambda x: x["page_number"])

        return document_data, system_prompt  # Return both document data and system prompt

    except Exception as e:
        logging.error(f"Error processing PDF file {file_name}: {e}")
        raise ValueError(f"Unable to process the file {file_name}. Error: {e}")
