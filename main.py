import streamlit as st
import json
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
        for uploaded_file in uploaded_files:
            # Check if the uploaded file is new or different from the previously uploaded files
            if uploaded_file.name not in st.session_state.documents:
                st.session_state.documents[uploaded_file.name] = None  # Initialize with None

                try:
                    with st.spinner(f'Processing {uploaded_file.name}...'):
                        st.session_state.documents[uploaded_file.name] = process_pdf_pages(uploaded_file)
                    st.success(f"{uploaded_file.name} processed successfully!")
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {e}")
            else:
                st.info(f"{uploaded_file.name} is already uploaded.")

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
        for chat in st.session_state.chat_history:
            st.markdown(f"<div style='text-align: right; color: #444; background-color: #EEE; border-radius: 10px; padding: 10px; margin: 5px 0;'>{chat['question']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: left; color: #444; background-color: #F9F9F9; border-radius: 10px; padding: 10px; margin: 5px 0;'>{chat['answer']}</div>", unsafe_allow_html=True)
            st.markdown("---")

    # Display the chat history
    display_chat()

    # Input for user questions with better style and handling
    st.markdown("<p style='color: #555;'>Type your question below:</p>", unsafe_allow_html=True)
    prompt = st.text_input("Ask a question", key="chat_input", placeholder="E.g., What is the summary of page 1?")

    if prompt:
        handle_question(prompt)
        display_chat()  # Re-display the chat after adding the new entry

