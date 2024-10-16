import fitz
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.file_conversion import convert_office_to_pdf
from utils.llm_interaction import summarize_page, get_image_explanation, generate_system_prompt
import io
import base64
import logging
from PIL import Image

# Set up logging
logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    return ' '.join(text.split())

def compress_image(image_data, max_size=(1024, 1024), quality=55):
    """Compress image to reduce size before sending to server."""
    try:
        image = Image.open(io.BytesIO(image_data))  # Open image from byte data
        image = image.convert("RGB")  # Ensure it's in RGB format (JPEG doesn't support RGBA)
        
        # Resize image to fit within the max_size while preserving aspect ratio
        image.thumbnail(max_size, Image.LANCZOS)  # Use LANCZOS for better quality
        
        # Save the image to a byte buffer with specified quality
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality)  # Use JPEG format for compression
        buffer.seek(0)
        
        return buffer.getvalue()

    except Exception as e:
        logging.error(f"Error compressing image: {e}")
        return image_data  # Return original data if compression fails

def detect_ocr_images_and_vector_graphics_in_pdf(page, ocr_text_threshold=0.19):
    """Detect pages with OCR images or vector graphics."""
    detected_pages = []
    images = page.get_images(full=True)
    text = page.get_text("text")
    text_blocks = page.get_text("blocks")
    vector_graphics_detected = any(page.get_drawings())
    page_area = page.rect.width * page.rect.height
    text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
    text_coverage = text_area / page_area
        
    
    if text_area==0:
        pix = page.get_pixmap() 
        img_data = pix.tobytes("png")
        pix = None
        compressed_img_data = compress_image(img_data)
        base64_image = base64.b64encode(compressed_img_data).decode("utf-8")
        return base64_image
        
    elif (images or vector_graphics_detected) and text.strip():
        if text_coverage < ocr_text_threshold:
            pix = page.get_pixmap() 
            img_data = pix.tobytes("png")
            pix = None
            compressed_img_data = compress_image(img_data)
            base64_image = base64.b64encode(compressed_img_data).decode("utf-8")
            return base64_image
                
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
                "full_text": text,# Adding full text to batch data
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
        full_textr = ""
        for page_numberr in range(total_pages):
            pager = pdf_document.load_page(page_numberr)
            full_textr += pager.get_text("text").strip() + " "  # Concatenate all text

        # Generate system prompt from full text
        system_prompt =  generate_system_prompt(full_textr)
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
        return document_data, system_prompt

    except Exception as e:
        logging.error(f"Error processing PDF file {file_name}: {e}")
        raise ValueError(f"Unable to process the file {file_name}. Error: {e}")
