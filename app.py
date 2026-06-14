import os
import json
import io
import re
from datetime import datetime
from flask import (
    Flask, request, render_template, redirect,
    url_for, flash, send_file, jsonify, session
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

from utils.database import init_db, save_policy, get_all_policies, get_policy_by_id, delete_policy
from utils.pdf_reader import extract_text_from_pdf
from utils.gemini_analyzer import analyze_policy

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 10))
MAX_CONTENT_LENGTH = MAX_FILE_MB * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database on startup
with app.app_context():
    init_db()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", max_mb=MAX_FILE_MB)


@app.route("/upload", methods=["POST"])
def upload():
    if "pdf_file" not in request.files:
        flash("No file selected. Please choose a PDF file.", "danger")
        return redirect(url_for("index"))

    file = request.files["pdf_file"]

    if file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Invalid file type. Only PDF files are accepted.", "danger")
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
    unique_filename = timestamp + filename
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)

    try:
        file.save(filepath)
    except Exception as e:
        flash(f"Failed to save file: {str(e)}", "danger")
        return redirect(url_for("index"))

    # Extract text
    try:
        text = extract_text_from_pdf(filepath)
    except FileNotFoundError:
        flash("File was not saved correctly. Please try again.", "danger")
        return redirect(url_for("index"))
    except ValueError as e:
        flash(f"PDF Error: {str(e)}", "danger")
        _cleanup(filepath)
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Could not read PDF: {str(e)}", "danger")
        _cleanup(filepath)
        return redirect(url_for("index"))

    # AI Analysis
    try:
        result = analyze_policy(text)
    except ValueError as e:
        flash(f"AI Error: {str(e)}", "danger")
        _cleanup(filepath)
        return redirect(url_for("index"))
    except RuntimeError as e:
        flash(f"AI Service Error: {str(e)}", "danger")
        _cleanup(filepath)
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Unexpected error during analysis: {str(e)}", "danger")
        _cleanup(filepath)
        return redirect(url_for("index"))

    # Save to database
    try:
        policy_id = save_policy(
            policy_name=result["policy_name"],
            description=result["description"],
            benefits=result["benefits"],
            eligibility=result["eligibility"],
            last_date=result["last_date"],
            filename=unique_filename,
        )
    except Exception as e:
        flash(f"Database error: {str(e)}", "danger")
        _cleanup(filepath)
        return redirect(url_for("index"))

    return redirect(url_for("result", policy_id=policy_id))


@app.route("/result/<int:policy_id>")
def result(policy_id):
    policy = get_policy_by_id(policy_id)
    if not policy:
        flash("Policy not found.", "danger")
        return redirect(url_for("index"))

    policy = _parse_policy(policy)
    return render_template("result.html", policy=policy)


@app.route("/history")
def history():
    search = request.args.get("search", "").strip()
    policies = get_all_policies(search if search else None)
    policies = [_parse_policy(p) for p in policies]
    return render_template("history.html", policies=policies, search=search)


@app.route("/delete/<int:policy_id>", methods=["POST"])
def delete(policy_id):
    policy = get_policy_by_id(policy_id)
    if policy:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], policy.get("filename", ""))
        _cleanup(filepath)
        delete_policy(policy_id)
        flash("Policy deleted successfully.", "success")
    else:
        flash("Policy not found.", "danger")
    return redirect(url_for("history"))


@app.route("/download/txt/<int:policy_id>")
def download_txt(policy_id):
    policy = get_policy_by_id(policy_id)
    if not policy:
        flash("Policy not found.", "danger")
        return redirect(url_for("history"))

    policy = _parse_policy(policy)
    content = _build_txt(policy)
    buf = io.BytesIO(content.encode("utf-8"))
    safe_name = re.sub(r"[^\w\s-]", "", policy["policy_name"])[:50].strip().replace(" ", "_")
    return send_file(buf, as_attachment=True,
                     download_name=f"{safe_name}_summary.txt",
                     mimetype="text/plain")


@app.route("/download/pdf/<int:policy_id>")
def download_pdf(policy_id):
    policy = get_policy_by_id(policy_id)
    if not policy:
        flash("Policy not found.", "danger")
        return redirect(url_for("history"))

    policy = _parse_policy(policy)
    buf = _build_pdf(policy)
    safe_name = re.sub(r"[^\w\s-]", "", policy["policy_name"])[:50].strip().replace(" ", "_")
    return send_file(buf, as_attachment=True,
                     download_name=f"{safe_name}_summary.pdf",
                     mimetype="application/pdf")


@app.errorhandler(413)
def too_large(e):
    flash(f"File too large. Maximum size is {MAX_FILE_MB} MB.", "danger")
    return redirect(url_for("index"))


@app.errorhandler(404)
def not_found(e):
    return render_template("index.html", max_mb=MAX_FILE_MB), 404


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _cleanup(filepath):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass


def _parse_policy(policy):
    """Parse JSON-stored list fields back to Python lists."""
    for field in ["benefits", "eligibility"]:
        val = policy.get(field)
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                policy[field] = parsed if isinstance(parsed, list) else [parsed]
            except (json.JSONDecodeError, TypeError):
                policy[field] = [val] if val else ["Not Specified"]
        elif not isinstance(val, list):
            policy[field] = ["Not Specified"]
    return policy


def _build_txt(policy):
    lines = [
        "=" * 60,
        "AI POLICY SUMMARIZER - POLICY SUMMARY",
        "=" * 60,
        "",
        f"Policy Name   : {policy['policy_name']}",
        f"Upload Date   : {policy['upload_date']}",
        f"Last Date     : {policy['last_date']}",
        "",
        "DESCRIPTION",
        "-" * 40,
        policy['description'],
        "",
        "BENEFITS",
        "-" * 40,
    ]
    for b in policy["benefits"]:
        lines.append(f"  • {b}")
    lines += [
        "",
        "ELIGIBILITY CRITERIA",
        "-" * 40,
    ]
    for e in policy["eligibility"]:
        lines.append(f"  • {e}")
    lines += ["", "=" * 60, "Generated by AI Policy Summarizer", "=" * 60]
    return "\n".join(lines)


def _build_pdf(policy):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    accent = colors.HexColor("#1a56db")
    dark = colors.HexColor("#1e293b")
    muted = colors.HexColor("#64748b")

    title_style = ParagraphStyle("title", parent=styles["Title"],
                                 fontSize=22, textColor=accent,
                                 spaceAfter=4, fontName="Helvetica-Bold")
    header_style = ParagraphStyle("header", parent=styles["Normal"],
                                  fontSize=13, textColor=dark,
                                  spaceBefore=14, spaceAfter=4,
                                  fontName="Helvetica-Bold")
    body_style = ParagraphStyle("body", parent=styles["Normal"],
                                fontSize=10, textColor=dark,
                                leading=15)
    meta_style = ParagraphStyle("meta", parent=styles["Normal"],
                                fontSize=9, textColor=muted)
    bullet_style = ParagraphStyle("bullet", parent=styles["Normal"],
                                  fontSize=10, textColor=dark,
                                  leading=16, leftIndent=12)

    story = []

    story.append(Paragraph("AI Policy Summarizer", ParagraphStyle(
        "brand", parent=styles["Normal"], fontSize=10,
        textColor=accent, fontName="Helvetica-Bold", spaceAfter=2)))
    story.append(Paragraph(policy["policy_name"], title_style))
    story.append(Paragraph(f"Uploaded: {policy['upload_date']}", meta_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=accent))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Description", header_style))
    story.append(Paragraph(policy["description"], body_style))

    story.append(Paragraph("Benefits", header_style))
    for b in policy["benefits"]:
        story.append(Paragraph(f"• {b}", bullet_style))

    story.append(Paragraph("Eligibility Criteria", header_style))
    for e in policy["eligibility"]:
        story.append(Paragraph(f"• {e}", bullet_style))

    story.append(Paragraph("Last Date to Apply", header_style))
    story.append(Paragraph(policy["last_date"], body_style))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=muted))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Generated by AI Policy Summarizer", ParagraphStyle(
        "footer", parent=styles["Normal"], fontSize=8, textColor=muted,
        alignment=TA_CENTER)))

    doc.build(story)
    buf.seek(0)
    return buf


if __name__ == "__main__":
    app.run(debug=True, port=5000)
