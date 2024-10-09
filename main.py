import streamlit as st
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.pdf_processing import process_pdf_pages
from utils.llm_interaction import ask_question

# Initialize session state variables to avoid reloading and reprocessing
if 'documents' not in st.session_state:
    st.session_state.documents = {}  # Dictionary to hold document name and data
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'question_input' not in st.session_state:
    st.session_state.question_input = ""

# Function to handle user question and get the answer
def handle_question(prompt):
    if prompt:
        try:
            # Use the cached document data and chat history for the query
            answer = ask_question(st.session_state.documents, prompt, st.session_state.chat_history)
            # Add the question-answer pair to the chat history
            st.session_state.chat_history.append({"question": prompt, "answer": answer})
        except Exception as e:
            st.error(f"Error in processing question: {e}")

# Function to display document data
def display_documents_data():
    for doc_name, doc_data in st.session_state.documents.items():
        st.subheader(f"Document: {doc_name}")
        for page in doc_data["pages"]:
            st.write(f"**Page {page['page_number']} Summary:**")
            st.write(page['text_summary'])
            if page['image_analysis']:
                st.write("**Image Analysis:**")
                for img in page['image_analysis']:
                    st.write(f"- Page {img['page_number']}: {img['explanation']}")
            st.markdown("---")  # Separator for pages

# Streamlit application title with modern styling
st.markdown("<h1 style='text-align: center; color: #4B9CD3;'>docQuest: Document AI Assistant</h1>", unsafe_allow_html=True)

# Sidebar for file upload and document information
with st.sidebar:
    st.subheader("docQuest: File Upload")

    # File uploader with updated error handling for better user feedback
    uploaded_files = st.file_uploader(
        "Upload files here",
        type=["pdf", "docx", "xlsx", "pptx"],
        accept_multiple_files=True,
        help="Supports multiple document formats: PDF, DOCX, XLSX, PPTX"
    )

    if uploaded_files:
        # Use ThreadPoolExecutor to process multiple documents concurrently
        def process_document(uploaded_file):
            try:
                with st.spinner(f'Processing {uploaded_file.name}...'):
                    document_data = process_pdf_pages(uploaded_file)
                return uploaded_file.name, document_data
            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {e}")
                return uploaded_file.name, None

        # Initialize ThreadPoolExecutor to process documents in parallel
        if uploaded_files:
            futures = []
            with ThreadPoolExecutor() as executor:
                for uploaded_file in uploaded_files:
                    futures.append(executor.submit(process_document, uploaded_file))

                # Display a progress bar for processing
                progress_bar = st.progress(0)
                for i, future in enumerate(as_completed(futures), 1):
                    doc_name, document_data = future.result()
                    if document_data:  # Check if the document was successfully processed
                        st.session_state.documents[doc_name] = document_data
                        st.success(f"{doc_name} processed successfully!")
                    else:
                        st.error(f"Failed to process {doc_name}")
                    progress_bar.progress(i / len(uploaded_files))

    # Download button for complete analysis
    if st.session_state.documents:
        download_data = json.dumps(st.session_state.documents, indent=4)
        st.download_button(
            label="Download Document Analysis",
            data=download_data,
            file_name="document_analysis.json",
            mime="application/json",
            help="Download the detailed analysis of uploaded documents."
        )

# Main page for chat interaction
if st.session_state.documents:
    st.subheader("Ask questions about your documents")

    # Function to display chat history dynamically
    def display_chat():
        if st.session_state.chat_history:  # Ensure there's chat history before displaying
            for chat in st.session_state.chat_history:
                st.markdown(f"<div style='text-align: right; border-radius: 10px; padding: 10px; margin: 5px 0; background-color: #e0f7fa;'>{chat['question']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align: left; border-radius: 10px; padding: 10px; margin: 5px 0; background-color: #ffe0b2;'>{chat['answer']}</div>", unsafe_allow_html=True)
                st.markdown("---")

    # Display the chat history
    display_chat()

    # Input for user questions with ChatGPT-like interface using `st.chat_input()`
    prompt = st.chat_input("Let me know what you want to know about your documents...", key="chat_input")

    if prompt:
        handle_question(prompt)
        display_chat()  # Re-display the chat after adding the new entry
