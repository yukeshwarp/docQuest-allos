import streamlit as st
from concurrent.futures import ThreadPoolExecutor
import base64
from pdf_processing import process_pdf_pages
from azure_api import ask_question

# Initialize session state variables to avoid reloading and reprocessing
if 'documents' not in st.session_state:
    st.session_state.documents = {}  # Dictionary to hold document name and data
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'comparison_mode' not in st.session_state:
    st.session_state.comparison_mode = False

# Function to handle user question and get the answer
def handle_question(prompt):
    if prompt:
        # Use the cached document data for the query
        answer = ask_question(st.session_state.documents, prompt)
        # Add the question-answer pair to the chat history
        st.session_state.chat_history.append({"question": prompt, "answer": answer})

# Streamlit application title
st.title("docQuest - Comparative Study")

# Sidebar for file upload and document information
with st.sidebar:
    st.subheader("docQuest")
    
    # File uploader for multiple files
    uploaded_files = st.file_uploader("Upload and manage files here", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Check if the uploaded file is new or different from the previously uploaded files
            if uploaded_file.name not in st.session_state.documents:
                st.session_state.documents[uploaded_file.name] = None  # Initialize with None

                # Process the PDF if not already processed
                with st.spinner(f'Processing {uploaded_file.name}...'):
                    st.session_state.documents[uploaded_file.name] = process_pdf_pages(uploaded_file)
                st.success(f"{uploaded_file.name} processed successfully! Let's explore your documents.")

# Main page for comparative study and chat interaction
if st.session_state.documents:
    st.subheader("Compare Documents")

    # Show document selection options for comparison
    document_names = list(st.session_state.documents.keys())
    doc1_name = st.selectbox("Select Document 1", document_names, key="doc1")
    doc2_name = st.selectbox("Select Document 2", document_names, key="doc2")
    
    # Display summaries of the selected documents side by side for comparison
    if doc1_name and doc2_name:
        st.markdown("### Document Summaries")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Summary of {doc1_name}**")
            summary1 = "\n".join([page['text_summary'] for page in st.session_state.documents[doc1_name]["pages"]])
            st.text_area(f"Summary of {doc1_name}", value=summary1, height=300, key="summary1")

        with col2:
            st.markdown(f"**Summary of {doc2_name}**")
            summary2 = "\n".join([page['text_summary'] for page in st.session_state.documents[doc2_name]["pages"]])
            st.text_area(f"Summary of {doc2_name}", value=summary2, height=300, key="summary2")
    
    # Enable comparison mode based on user input
    st.session_state.comparison_mode = st.checkbox("Enable comparison mode")

    # Input for user questions using chat input, specifically for comparative study
    if st.session_state.comparison_mode:
        st.subheader("Ask Questions About the Comparison")
        
        # Create a placeholder container for chat history
        chat_placeholder = st.empty()

        # Function to display chat history dynamically
        def display_chat():
            with chat_placeholder.container():
                if st.session_state.chat_history:
                    st.subheader("Chats", divider="orange")
                    for chat in st.session_state.chat_history:
                        # ChatGPT-like alignment: user input on the right, assistant response on the left                
                        user_chat = f"<div style='float: right; display: inline-block; margin: 5px; border-radius: 8px; padding: 10px; margin-left: 3vw;'> {chat['question']}</div>"
                        assistant_chat = f"<div style='float: left; display: inline-block; margin: 5px; border-radius: 8px; padding: 10px; margin-right: 3vw;'> {chat['answer']}</div>"                    
                        st.markdown(f"\n")
                        st.markdown(user_chat, unsafe_allow_html=True)
                        st.markdown(assistant_chat, unsafe_allow_html=True)
                        st.markdown("---")

        # Display the chat history
        display_chat()

        # Input for user questions
        prompt = st.chat_input("Ask about the differences or similarities between the documents..", key="chat_input")
        
        # Check if the prompt has been updated
        if prompt:
            handle_question(prompt)  # Call the function to handle the question
            display_chat()  # Re-display the chat after adding the new entry

    # Optionally, display image analysis for both documents side by side
    if st.checkbox("Show Image Analysis"):
        st.markdown("### Image Analysis Comparison")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Image Analysis of {doc1_name}**")
            img_analysis1 = [
                page["image_analysis"] for page in st.session_state.documents[doc1_name]["pages"]
            ]
            st.json(img_analysis1)

        with col2:
            st.markdown(f"**Image Analysis of {doc2_name}**")
            img_analysis2 = [
                page["image_analysis"] for page in st.session_state.documents[doc2_name]["pages"]
            ]
            st.json(img_analysis2)
