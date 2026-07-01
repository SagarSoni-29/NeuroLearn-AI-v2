from flask import Flask, render_template, request, redirect, session, jsonify
from dotenv import load_dotenv
from groq import Groq
import os
import json
import bcrypt
from PyPDF2 import PdfReader
from docx import Document
from werkzeug.utils import secure_filename
from uuid import uuid4
from dynamodb_service import create_user, get_user, save_quiz, get_user_quizzes
from dynamodb_service import update_xp , update_quiz_count, get_progress, init_progress, update_login_streak

# Load ENV
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# GROQ Config
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Upload Folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helpers

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


# AI Function
def ask_ai(prompt):

    try:

        response = client.chat.completions.create(

            model="llama-3.1-8b-instant",

            messages=[
                {
                    "role":"user",
                    "content":prompt
                }
            ],

            temperature=0.7,
            max_tokens=1024
        )

        return response.choices[0].message.content

    except Exception as e:

        return f"Error : {str(e)}"


# Extract PDF Text
def extract_pdf(file_path):

    text = ""

    pdf = PdfReader(file_path)

    for page in pdf.pages:
        content = page.extract_text()

        if content:
            text += content

    return text


# Extract DOCX Text
def extract_docx(file_path):

    doc = Document(file_path)

    text = ""

    for para in doc.paragraphs:
        text += para.text + ""

    return text


# Home
@app.route("/")
def home():
    return render_template("index.html")


# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        # Hash password
        hashed_password = hash_password(password)
        
        existing_user = get_user(username)

        if existing_user:
            return "User already exists"

        # Save in AWS DynamoDB
        user_id = str(uuid4())

        create_user(
            user_id=user_id,
            username=username,
            password=hashed_password
        )

        init_progress(user_id)
        session["user"] = user_id

        return redirect("/login")

    return render_template("signup.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = get_user(username)

        if user:

            if verify_password(password, user["password"]):

                session["user"] = user["user_id"]
                session["username"] = user["username"]

                update_login_streak(user["user_id"])

                return redirect("/dashboard")

        return "Invalid Credentials"

    return render_template("login.html")


# Dashboard
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/login")

    return render_template(
    "dashboard.html",
    user=session.get("username", "User")
)


# CHATBOT
@app.route("/chat", methods=["POST"])
def chat():

    data = request.json

    message = data["message"]

    prompt = f"""
    You are NeuroLearn AI,
    a professional educational AI assistant.

    Give answers in a clean professional format.

    Rules:
    - Use headings
    - Use bullet points
    - Keep spacing proper
    - Explain clearly
    - Make output visually structured

    USER QUESTION:
    {message}
    """

    response = ask_ai(prompt)

    return jsonify({"response": response})


# Summarizer
@app.route("/summarize", methods=["POST"])
def summarize():

    data = request.json
    notes = data["notes"]

    prompt = f"Summarize these notes:{notes}"

    response = ask_ai(prompt)

    return jsonify({"summary": response})


# QUIZ Generator
@app.route("/quiz", methods=["POST"])
def quiz():

    if "user" not in session:
        return jsonify({"error": "Please login first"})

    data = request.json
    topic = data["topic"]

    prompt = f"Generate 5 quiz questions with answers on {topic}"

    response = ask_ai(prompt)

    quiz_id = str(uuid4())

    save_quiz(
    quiz_id=quiz_id,
    user_id=session["user"],
    topic=topic,
    quiz_content=response
    )
    update_xp(session["user"], 10)
    update_quiz_count(session["user"])
    

    return jsonify({"quiz": response})

# quiz history

@app.route("/quiz-history")
def quiz_history():

    if "user" not in session:
        return redirect("/login")

    quizzes = get_user_quizzes(session["user"])

    return render_template("quiz_history.html", quizzes=quizzes)

# Document Chat
@app.route("/upload", methods=["POST"])
def upload():

    file = request.files["file"]

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    file.save(filepath)

    extracted_text = ""

    if filename.endswith(".pdf"):
        extracted_text = extract_pdf(filepath)

    elif filename.endswith(".docx"):
        extracted_text = extract_docx(filepath)

    question = request.form["question"]

    prompt = f"""
    Answer the question based on document.

    DOCUMENT:
    {extracted_text}

    QUESTION:
    {question}
    """

    response = ask_ai(prompt)

    return jsonify({"answer": response})

# Progress

@app.route("/progress")
def progress():

    if "user" not in session:
        return redirect("/login")

    data = get_progress(session["user"])

    badges = []

    if data["quizzes_taken"] >= 5:
        badges.append("🏅 Beginner Learner")

    if data["quizzes_taken"] >= 10:
        badges.append("🎯 Quiz Master")

    if data["xp"] >= 100:
        badges.append("🧠 Scholar")

    if data["streak"] >= 3:
        badges.append("🔥 Consistent Learner")

    return render_template(
        "progress.html",
        progress=data,
        badges=badges
    )


# Logout
@app.route("/logout")
def logout():

    session.pop("user", None)
    return redirect("/")

# Main
if __name__ == "__main__":
    app.run(debug=True , threaded=True)
