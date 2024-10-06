import fitz  # PyMuPDF
import base64
from azure_api import get_image_explanation, summarize_page
from concurrent.futures import ThreadPoolExecutor

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    cleaned_text = ' '.join(word for word in text.split())
    return cleaned_text

def detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, page_number, ocr_text_threshold=0.1):
    """Detect OCR images or vector graphics in a single page."""
    page = pdf_document.load_page(page_number)
    images = page.get_images(full=True)
    text = page.get_text("text")
    text_blocks = page.get_text("blocks")
    vector_graphics_detected = any(page.get_drawings())

    if (images or vector_graphics_detected) and text.strip():
        page_area = page.rect.width * page.rect.height
        text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
        text_coverage = text_area / page_area

        if text_coverage < ocr_text_threshold:
            pix = page.get_pixmap() 
            img_data = pix.tobytes("png")
            base64_image = base64.b64encode(img_data).decode("utf-8")
            return (page_number + 1, base64_image)
    
    return None

def process_single_page(pdf_document, page_number, previous_summary):
    """Process a single page: summarize and detect images."""
    page = pdf_document.load_page(page_number)
    text = page.get_text("text").strip()
    preprocessed_text = remove_stopwords_and_blanks(text)
    
    # Summarize the page
    summary = summarize_page(preprocessed_text, previous_summary, page_number + 1)
    
    # Detect images or graphics on the page
    detected_image_data = detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, page_number, 0.18)
    image_analysis = []

    if detected_image_data:
        img_page, base64_image = detected_image_data
        if img_page == page_number + 1:
            image_explanation = get_image_explanation(base64_image)
            image_analysis.append({"page_number": img_page, "explanation": image_explanation})

    return {
        "page_number": page_number + 1,
        "text_summary": summary,
        "image_analysis": image_analysis
    }

def process_pdf_pages(pdf_document, document_name):
    """Process each page and extract image analysis and summaries for comparative study."""
    document_data = {"pages": [], "document_name": document_name}
    previous_summary = ""

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        text = page.get_text("text").strip()
        
        # Summarize the page with document context
        summary = summarize_page(text, previous_summary, page_number + 1, document_name)
        previous_summary = summary
        
        # Detect images or graphics on the page (using your OCR logic)
        detected_images = detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, 0.18)
        image_analysis = []

        for img_page, base64_image in detected_images:
            if img_page == page_number + 1:
                # Analyze the image with the document context
                image_explanation = get_image_explanation(base64_image, document_name)
                image_analysis.append({"page_number": img_page, "explanation": image_explanation})

        # Store the extracted data in JSON format with document context
        document_data["pages"].append({
            "page_number": page_number + 1,
            "text_summary": summary,
            "image_analysis": image_analysis
        })

    return document_data
