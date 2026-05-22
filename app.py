from flask import Flask, render_template, request, redirect, session
import mysql.connector
from scipy import io
import torch, os
from transformers import BertTokenizer, BertForSequenceClassification, data
import pytesseract
from PIL import Image
import seaborn as sns  
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix,classification_report

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)
app.secret_key = "secret123"

# DB
db = mysql.connector.connect(host="localhost", user="root", password="root", port=3307, database="fake_news_db")
cursor = db.cursor()

# Model
model = BertForSequenceClassification.from_pretrained("model/fake_news_model")
tokenizer = BertTokenizer.from_pretrained("model/fake_news_model")
model.eval()

def dataset_graph():

    # Load dataset
    df = pd.read_csv("fake_news_dataset.csv")   # place file in project folder

    # Group by source and count texts
    source_counts = df['source'].value_counts()

    # Plot graph
    plt.figure(figsize=(8,5))
    sns.barplot(x=source_counts.index, y=source_counts.values)
    plt.title("Number of News per Source", loc='center', fontsize=14)
    plt.xlabel("Source")
    plt.ylabel("Count")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("static/dataset_graph.png")
    plt.close()
dataset_graph()

# Functions
def extract_text(img_path):
    return pytesseract.image_to_string(Image.open(img_path))

def predict(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)
        pred = torch.argmax(probs).item()
        conf = probs[0][pred].item()
        labels = ["REAL", "FAKE"]
        return (labels[pred], conf)


# Routes
@app.route("/")
def home():
    return render_template("home.html")  
# Home page with User/Admin login buttons
@app.route("/user_login", methods=["GET","POST"])
def user_login():
    if request.method == "POST":
        u,p = request.form["username"], request.form["password"]
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s",(u,p))
        if cursor.fetchone():
            session["user"]=u
            return redirect("/index")
    return render_template("user_login.html")
@app.route("/admin_login", methods=["GET","POST"])
def admin_login():
    # Hardcoded credentials
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "admin"

    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["admin"] = u
            return redirect("/admin_dashboard")   # Admin dashboard route
        else:
            return render_template("admin_login.html", error="Invalid credentials")

    return render_template("admin_login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        phone = request.form.get("phone")  # optional

        # Password validation
        if password != confirm_password:
            error = "Passwords do not match!"
            return render_template("register.html", error=error,username=username, email=email, phone=phone)

        # Optional: check duplicate username/email
        cursor.execute("SELECT * FROM users WHERE username=%s OR email=%s", (username, email))
        if cursor.fetchone():
            error = "Username or Email already exists!"
            return render_template("register.html", error=error,
                                   username=username, email=email, phone=phone)

        # ✅ Insert all fields
        cursor.execute(
            "INSERT INTO users(username, email, password, phone) VALUES(%s,%s,%s,%s)",
            (username, email, password, phone)
        )
        db.commit()

        return redirect("/user_login")
    return render_template("register.html")
from flask import Flask, render_template, session, redirect
import mysql.connector
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time   # needed for timestamp

@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin_login")
    
    # Fetch users and predictions
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM predictions")
    predictions = cursor.fetchall()

    # Timestamp for cache-busting images
    timestamp = int(time.time())

    # ----------------------------
    # Fake vs Real News Graph
    # ----------------------------
    cursor.execute("SELECT result, COUNT(*) FROM predictions GROUP BY result")
    data = cursor.fetchall()
    labels = [row[0].upper() for row in data]
    values = [row[1] for row in data]

    plt.figure(figsize=(6,4))
    plt.bar(labels, values, color=['green','red'])
    plt.title("Fake vs Real News")
    plt.xlabel("News Type")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig("static/graph.png")
    plt.close()
    return render_template("admin_dashboard.html", users=users, predictions=predictions, timestamp=timestamp)
    
        
from PIL import Image
import pytesseract

@app.route("/index", methods=["GET","POST"])
def index():
    if "user" not in session:
        return redirect("/")

    result, conf, text = "", "", ""

    if request.method == "POST":

        file = request.files.get("image")

        # ✅ If image uploaded → process directly (NO saving)
        if file and file.filename != "":
            img = Image.open(file.stream)   #  Direct processing
            text = pytesseract.image_to_string(img)

        # ✅ If text entered
        else:
            text = request.form.get("news")

        # Prediction
        result, conf = predict(text)

        # Save to DB
        cursor.execute(
            "INSERT INTO predictions(username, news_text, result, confidence) VALUES(%s,%s,%s,%s)",
            (session["user"], text, result, conf)
        )
        db.commit()

    return render_template("index.html", result=result, confidence=conf, text=text)

@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/user_login")  # protect route
    username = session["user"]  # get logged-in user
    cursor.execute("SELECT * FROM predictions WHERE username=%s", (username,))
    data = cursor.fetchall()
    return render_template("history.html", data=data)

import matplotlib
matplotlib.use('Agg')   
import matplotlib.pyplot as plt

@app.route("/graph")
def graph():
    cursor.execute("SELECT result, COUNT(*) FROM predictions GROUP BY result")
    data = cursor.fetchall()


    labels = [row[0].upper() for row in data]
    values = [row[1] for row in data]
    plt.figure(figsize=(6,4))
    plt.bar(labels, values, color=['green','red'])
    plt.title("Fake vs Real News")
    plt.xlabel("News Type")
    plt.ylabel("Count")
    plt.savefig("static/graph.png")
    plt.close()
    return render_template("graph.html")

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    # Only admin can delete
    if "admin" not in session:
        return redirect("/admin_login")
    # Optional: delete user's predictions first to avoid foreign key issues
    cursor.execute("DELETE FROM predictions WHERE username=(SELECT username FROM users WHERE id=%s)", (user_id,))
    db.commit()
    # Delete user
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    db.commit()
    return redirect("/admin_dashboard")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

app.run(debug=True)
