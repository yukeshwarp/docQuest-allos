import streamlit as st
import json
from utils.pdf_processing import process_pdf_pages
from utils.llm_interaction import ask_question

# Initialize session state variables
if 'documents' not in st.session_state:
    st.session_state.documents = {}
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Function to handle user question
def handle_question(prompt):
    if prompt:
        try:
            with st.spinner('Generating answer...'):
                # Get response from the AI model
                answer = ask_question(
                    st.session_state.documents, prompt, st.session_state.chat_history
                )
            # Add the question-answer pair to the chat history
            st.session_state.chat_history.append({"question": prompt, "answer": answer})
            # Update the chat display
            display_chat()
        except Exception as e:
            st.error(f"Error processing question: {e}")

# Sidebar for file upload and document information
with st.sidebar:
    st.subheader("📄 Upload Your Documents")

    # File uploader
    uploaded_files = st.file_uploader(
        "Upload files here",
        type=["pdf", "docx", "xlsx", "pptx"],
        accept_multiple_files=True,
        help="Supports PDF, DOCX, XLSX, and PPTX formats.",
    )

    if uploaded_files:
        new_files = []
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.documents:
                new_files.append(uploaded_file)
            else:
                st.info(f"{uploaded_file.name} is already uploaded.")

        if new_files:
            # Use a placeholder to show progress
            progress_text = st.empty()
            progress_bar = st.progress(0)
            total_files = len(new_files)

            for i, uploaded_file in enumerate(new_files):
                try:
                    progress_text.text(
                        f'Processing {uploaded_file.name} ({i+1}/{total_files})...'
                    )
                    # Process the document and cache the result
                    document_data = process_pdf_pages(uploaded_file)
                    st.session_state.documents[uploaded_file.name] = document_data
                    st.success(f"{uploaded_file.name} processed successfully!")
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {e}")
                progress_bar.progress((i + 1) / total_files)
            progress_text.text("Processing complete.")
            progress_bar.empty()

    if st.session_state.documents:
        download_data = json.dumps(st.session_state.documents, indent=4)
        st.download_button(
            label="Download Document Analysis",
            data=download_data,
            file_name="document_analysis.json",
            mime="application/json",
        )

# Main Page - Chat Interface
st.title("💬 docQuest AI Assistant")

if st.session_state.documents:
    st.subheader("Ask me anything about your documents!")

    # Placeholder for chat history
    chat_placeholder = st.container()

    # Function to display chat history dynamically
    def display_chat():
        with chat_placeholder:
            st.write("")  # Clear previous chat
            for chat in st.session_state.chat_history:
                user_message = f"""
                <div style='background-color:#D3EBCD; padding:10px; border-radius:10px; margin:5px 0; text-align:right;'>
                    <strong>User:</strong> {chat['question']}
                </div>
                """
                assistant_message = f"""
                <div style='background-color:#FFE699; padding:10px; border-radius:10px; margin:5px 0; text-align:left;'>
                    <strong>Assistant:</strong> {chat['answer']}
                </div>
                """
                st.markdown(user_message, unsafe_allow_html=True)
                st.markdown(assistant_message, unsafe_allow_html=True)

    # Display the chat history
    display_chat()

    # Chat input field using st.chat_input
    prompt = st.chat_input("Let me know what you want to know about your documents...", key="chat_input")

    # Check if the prompt has been updated
    if prompt:
        handle_question(prompt)  # Call the function to handle the question
