import streamlit as st
import json
from utils.pdf_processing import process_pdf_pages
from utils.llm_interaction import ask_question
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# Function to process files in parallel
def process_files_in_parallel(files):
    document_data = {}
    with ThreadPoolExecutor() as executor:
        # Use ThreadPoolExecutor to process files concurrently
        future_to_file = {executor.submit(process_pdf_pages, f): f for f in files}
        total_files = len(files)
        
        progress_text = st.empty()
        progress_bar = st.progress(0)

        for i, future in enumerate(as_completed(future_to_file)):
            file = future_to_file[future]
            try:
                result = future.result()  # Get the processed PDF result
                document_data[file.name] = result
                st.session_state.documents[file.name] = result
                st.success(f"{file.name} processed successfully!")
            except Exception as e:
                st.error(f"Error processing {file.name}: {e}")
            
            # Update progress bar
            progress_bar.progress((i + 1) / total_files)
            progress_text.text(f"Processing {i + 1}/{total_files} files complete.")
        
        progress_text.text("Processing complete.")
        progress_bar.empty()

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
        new_files = [f for f in uploaded_files if f.name not in st.session_state.documents]

        if new_files:
            with st.spinner('Processing documents...'):
                process_files_in_parallel(new_files)  # Process files in parallel

    if st.session_state.documents:
        download_data = json.dumps(st.session_state.documents, indent=4)
        st.download_button(
            label="Download Document Analysis",
            data=download_data,
            file_name="document_analysis.json",
            mime="application/json",
        )

# Main Page - Chat Interface
st.title("💬 docQuest : Document Intelligence")

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
                <div style='padding:10px; border-radius:10px; margin:5px 0; text-align:right;'> {chat['question']}
                </div>
                """
                assistant_message = f"""
                <div style='padding:10px; border-radius:10px; margin:5px 0; text-align:left;'> {chat['answer']}
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
