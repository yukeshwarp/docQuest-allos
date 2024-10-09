import fitz
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.file_conversion import convert_office_to_pdf
from utils.llm_interaction import *
import io
import base64

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    cleaned_text = ' '.join(word for word in text.split())
    return cleaned_text

def detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, ocr_text_threshold=0.4):
    """Detect pages with OCR images or vector graphics."""
    detected_pages = []

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        images = page.get_images(full=True)
        text = page.get_text("text")

        text_blocks = page.get_text("blocks")
        vector_graphics_detected = any(page.get_drawings())
        page_area = page.rect.width * page.rect.height
        text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
        text_coverage = text_area / page_area
        pix = page.get_pixmap() 
        img_data = pix.tobytes("png")
        base64_image = base64.b64encode(img_data).decode("utf-8")
        if text_area == 0:
            detected_pages.append((page_number + 1, base64_image))
            
        elif (images or vector_graphics_detected) and text.strip():
            if text_coverage < ocr_text_threshold:
                detected_pages.append((page_number + 1, base64_image))
    return detected_pages

def process_page_batch(pdf_document, batch, ocr_text_threshold=0.4):
    """Process a batch of PDF pages and extract summaries and image analysis."""
    previous_summary = ""
    batch_data = []

    for page_number in batch:
        page = pdf_document.load_page(page_number)
        text = page.get_text("text").strip()
        preprocessed_text = remove_stopwords_and_blanks(text)

        # Summarize the page
        summary = summarize_page(preprocessed_text, previous_summary, page_number + 1)
        previous_summary = summary

        # Detect images or graphics on the page
        detected_images = detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, ocr_text_threshold)
        image_analysis = []

        for img_page, base64_image in detected_images:
            if img_page == page_number + 1:
                image_explanation = get_image_explanation(base64_image)
                image_analysis.append({"page_number": img_page, "explanation": image_explanation})

        # Store the extracted data
        batch_data.append({
            "page_number": page_number + 1,
            "text_summary": summary,
            "image_analysis": image_analysis
        })

    return batch_data

def process_page_batch(pdf_document, batch, ocr_text_threshold=0.4):
    """Process a batch of PDF pages and extract summaries and image analysis."""
    previous_summary = ""
    batch_data = []

    for page_number in batch:
        page = pdf_document.load_page(page_number)
        text = page.get_text("text").strip()
        preprocessed_text = remove_stopwords_and_blanks(text)

        summary = summarize_page(preprocessed_text, previous_summary, page_number + 1)
        previous_summary = summary

        detected_images = detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, ocr_text_threshold)
        image_analysis = [
            {"page_number": img_page, "explanation": get_image_explanation(base64_image)}
            for img_page, base64_image in detected_images if img_page == page_number + 1
        ]

        batch_data.append({
            "page_number": page_number + 1,
            "text_summary": summary,
            "image_analysis": image_analysis
        })

    return batch_data

def process_pdf_pages(uploaded_file):
    """Process the PDF pages in batches and extract summaries and image analysis."""
    file_name = uploaded_file.name
    
    # Check if the uploaded file is a PDF
    if file_name.lower().endswith('.pdf'):
        # If it's a PDF, read it directly into a BytesIO object
        pdf_stream = io.BytesIO(uploaded_file.read())
    else:
        # Convert the uploaded Office file to PDF if necessary
        pdf_stream = convert_office_to_pdf(uploaded_file)
    
    # Process the PDF document
    pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
    document_data = {"pages": [], "name": file_name}
    total_pages = len(pdf_document)
    
    # Batch size of 5 pages
    batch_size = 5
    page_batches = [range(i, min(i + batch_size, total_pages)) for i in range(0, total_pages, batch_size)]
    
    # Use ThreadPoolExecutor to process batches concurrently
    with ThreadPoolExecutor() as executor:
        future_to_batch = {executor.submit(process_page_batch, pdf_document, batch): batch for batch in page_batches}
        for future in as_completed(future_to_batch):
            batch_data = future.result()  # Get the result of processed batch
            document_data["pages"].extend(batch_data)
    
    # Close the PDF document after processing
    pdf_document.close()
    
    # Sort pages by page_number to ensure correct order
    document_data["pages"].sort(key=lambda x: x["page_number"])
    
    return document_data
