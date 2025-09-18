# investment_framework_app.py

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text, JSON, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from docx import Document
from PyPDF2 import PdfReader
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
DB_URL = os.getenv("DB_URL", "sqlite:///investment.db")

# Database setup
Base = declarative_base()
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

# Database models
class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    project_name = Column(String)
    sector = Column(String)
    country = Column(String)
    region = Column(String)
    status = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    description = Column(Text)

class FinancialData(Base):
    __tablename__ = 'financial_data'
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    capex = Column(Float)
    opex = Column(String)
    irr = Column(Float)
    npv = Column(Float)
    currency = Column(String)

class EnvironmentalData(Base):
    __tablename__ = 'environmental_data'
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    co2e_reduction = Column(String)
    carbon_intensity = Column(String)
    lifecycle_emissions = Column(String)
    emissions_profile = Column(JSON)
    data_source = Column(String)

Base.metadata.create_all(engine)

# Utility functions
def extract_text_from_pdf(file):
    reader = PdfReader(file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_project_fields(text):
    prompt = f"""
Extract the following fields from the document text:
- Project Name, Sector, Country, Region, Status, Start Date, End Date, Description
- Capex, Opex, IRR, NPV, CO₂e Reduction, Carbon Intensity, Lifecycle Emissions

Text:
{text}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Extract structured investment data from documents."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    return response['choices'][0]['message']['content']

def save_extracted_fields(data: dict):
    session = Session()
    try:
        project = Project(
            project_name=data.get("Project Name"),
            sector=data.get("Sector"),
            country=data.get("Country"),
            region=data.get("Region"),
            status=data.get("Status"),
            start_date=data.get("Start Date"),
            end_date=data.get("End Date"),
            description=data.get("Description")
        )
        session.add(project)
        session.flush()

        financial = FinancialData(
            project_id=project.id,
            capex=data.get("Capex"),
            opex=data.get("Opex"),
            irr=data.get("IRR"),
            npv=data.get("NPV"),
            currency="USD"
        )
        session.add(financial)

        environmental = EnvironmentalData(
            project_id=project.id,
            co2e_reduction=data.get("CO₂e Reduction"),
            carbon_intensity=data.get("Carbon Intensity"),
            lifecycle_emissions=data.get("Lifecycle Emissions"),
            emissions_profile={"Scope 1": 0, "Scope 2": 0.05, "Scope 3": 0},
            data_source="Extracted via NLP"
        )
        session.add(environmental)

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"❌ Error saving to DB: {e}")
        return False
    finally:
        session.close()

# Streamlit UI
st.set_page_config(page_title="AI Investment Framework", layout="wide")
st.title("📊 AI-Enhanced Investment Decision Framework")

st.markdown("### Upload Project Document (.pdf, .docx, .txt, .xlsx, .json)")
uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt", "xlsx", "csv", "json"])

if uploaded_file:
    file_type = uploaded_file.name.split(".")[-1]
    text = ""

    if file_type == "pdf":
        text = extract_text_from_pdf(uploaded_file)
    elif file_type == "docx":
        text = extract_text_from_docx(uploaded_file)
    elif file_type == "txt":
        text = uploaded_file.read().decode("utf-8")
    elif file_type in ["xlsx", "csv"]:
        df = pd.read_excel(uploaded_file) if file_type == "xlsx" else pd.read_csv(uploaded_file)
        st.dataframe(df)
    elif file_type == "json":
        data = json.load(uploaded_file)
        st.json(data)

    if text:
        st.text_area("📄 Extracted Text", text, height=300)

        if st.button("🧠 Extract Structured Data"):
            structured_output = extract_project_fields(text)
            try:
                structured_dict = eval(structured_output)
                st.markdown("### 🧾 Review & Edit Extracted Fields")
                editable_data = st.experimental_data_editor(structured_dict, num_rows="dynamic")

                if st.button("✅ Save to Database"):
                    success = save_extracted_fields(editable_data)
                    if success:
                        st.success("✅ Project data saved successfully.")
            except Exception as e:
                st.error(f"❌ Failed to parse extracted data: {e}")
