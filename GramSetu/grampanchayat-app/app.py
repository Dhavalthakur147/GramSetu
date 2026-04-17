from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from functools import wraps
from datetime import datetime, timezone
from uuid import uuid4

import pymysql
from flask import (
    Flask,
    abort,
    g,
    has_request_context,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from pymysql.cursors import DictCursor
from pymysql.err import IntegrityError, MySQLError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

SUPPORTED_LANGUAGES = ("en", "gu")
DEFAULT_LANGUAGE = "en"

SERVICE_LABELS = {
    "birth_certificate": {"en": "Birth Certificate", "gu": "જન્મ પ્રમાણપત્ર"},
    "income_certificate": {"en": "Income Certificate", "gu": "આવક પ્રમાણપત્ર"},
    "caste_certificate": {"en": "Caste Certificate", "gu": "જાતિ પ્રમાણપત્ર"},
    "ration_card_update": {"en": "Ration Card Update", "gu": "રેશન કાર્ડ અપડેટ"},
    "water_connection": {"en": "Water Connection", "gu": "પાણી કનેક્શન"},
}

SERVICE_STATUS_OPTIONS = ("submitted", "under_review", "approved", "rejected")
COMPLAINT_STATUS_OPTIONS = ("open", "in_progress", "resolved", "closed")
USER_ROLE_OPTIONS = ("citizen", "admin", "staff")
ADMIN_ROLE_OPTIONS = ("admin", "staff")
USER_STATUS_OPTIONS = ("active", "inactive")
FORM_FIELD_TYPES = ("text", "textarea", "number", "date", "tel", "email", "select", "file")
RESERVED_DYNAMIC_FIELD_NAMES = {
    "applicant_name",
    "mobile",
    "email",
    "request_id",
    "status",
    "supporting_documents",
    "supporting_evidence",
}
RESERVED_SERVICE_SLUGS = {
    "birth-certificate",
    "income-certificate",
    "caste-certificate",
    "ration-card-update",
    "water-connection",
    "track",
}
DEFAULT_SCHEME_FIELD_TEMPLATE = json.dumps(
    [
        {
            "name": "farmer_id",
            "label": "Farmer ID / Registration Number",
            "type": "text",
            "required": True,
            "placeholder": "Enter registered farmer ID",
        },
        {
            "name": "village_name",
            "label": "Village Name",
            "type": "text",
            "required": True,
            "placeholder": "Enter village name",
        },
        {
            "name": "land_area_acre",
            "label": "Land Area (Acre)",
            "type": "number",
            "required": True,
            "placeholder": "Example: 2.5",
        },
        {
            "name": "scheme_category",
            "label": "Scheme Category",
            "type": "select",
            "required": True,
            "options": ["Subsidy", "Equipment Support", "Training", "Financial Aid"],
        },
        {
            "name": "application_note",
            "label": "Application Note",
            "type": "textarea",
            "required": False,
            "placeholder": "Share any supporting details for verification.",
        },
    ],
    indent=2,
)

STATUS_LABELS = {
    "submitted": {"en": "Submitted", "gu": "સબમિટ થયેલ"},
    "under_review": {"en": "Under Review", "gu": "ચકાસણી હેઠળ"},
    "approved": {"en": "Approved", "gu": "મંજૂર"},
    "rejected": {"en": "Rejected", "gu": "નકારી દેવાયેલ"},
    "open": {"en": "Open", "gu": "ખુલ્લી"},
    "in_progress": {"en": "In Progress", "gu": "પ્રક્રિયામાં"},
    "resolved": {"en": "Resolved", "gu": "ઉકેલાયેલ"},
    "closed": {"en": "Closed", "gu": "બંધ"},
}

TEXT_TRANSLATIONS = {
    "gu": {
        "Government of Gujarat | Agriculture & Farmers Welfare Department": "ગુજરાત સરકાર | કૃષિ અને ખેડૂત કલ્યાણ વિભાગ",
        "Gujarati": "ગુજરાતી",
        "English": "English",
        "Helpline": "હેલ્પલાઇન",
        "Admin Panel": "એડમિન પેનલ",
        "Logout": "લોગઆઉટ",
        "Login": "લોગિન",
        "Register": "રજીસ્ટર",
        "GramSetu Portal": "ગ્રામસેતુ પોર્ટલ",
        "Digital Farmer Service Platform": "ડિજિટલ ખેડૂત સેવા પ્લેટફોર્મ",
        "Home": "હોમ",
        "About": "પરિચય",
        "Services": "સેવાઓ",
        "Complaints": "ફરિયાદો",
        "Notices": "જાહેર સૂચનાઓ",
        "Dashboard": "ડેશબોર્ડ",
        "Contact": "સંપર્ક",
        "GramSetu Digital Portal": "ગ્રામસેતુ ડિજિટલ પોર્ટલ",
        "Inspired by modern iKhedut-style government service experience.": "આધુનિક iKhedut જેવી સરકારી સેવા અનુભવથી પ્રેરિત.",
        "Admin": "એડમિન",
        "Digital Agriculture Mission": "ડિજિટલ કૃષિ મિશન",
        "Farmer First Online Services Portal": "ખેડૂત પ્રથમ ઑનલાઇન સેવા પોર્ટલ",
        "Apply for certificates, register complaints, track requests, and view real-time rural service updates from one digital platform.": "પ્રમાણપત્ર માટે અરજી કરો, ફરિયાદ નોંધાવો, અરજીઓ ટ્રેક કરો અને એક જ ડિજિટલ પ્લેટફોર્મ પર ગ્રામ્ય સેવાઓના લાઇવ અપડેટ જુઓ.",
        "Farmer Registration": "ખેડૂત નોંધણી",
        "Apply Schemes": "યોજનાઓ માટે અરજી",
        "Live Dashboard": "લાઇવ ડેશબોર્ડ",
        "Total Applications": "કુલ અરજીઓ",
        "Under Process": "પ્રક્રિયામાં",
        "Total Complaints": "કુલ ફરિયાદો",
        "Digital Efficiency": "ડિજિટલ કાર્યક્ષમતા",
        "About Portal": "પોર્ટલ વિશે",
        "Integrated e-Governance for Farmers": "ખેડૂતો માટે સંકલિત ઇ-ગવર્નન્સ",
        "This portal is inspired by iKhedut-style digital flow where farmers can access government services, submit scheme applications, and track each process through transparent status updates.": "આ પોર્ટલ iKhedut જેવી ડિજિટલ પ્રક્રિયાથી પ્રેરિત છે, જ્યાં ખેડૂતો સરકારી સેવાઓ મેળવી શકે છે, યોજનાઓ માટે અરજી કરી શકે છે અને પારદર્શક સ્ટેટસ અપડેટથી દરેક પ્રક્રિયા ટ્રેક કરી શકે છે.",
        "Single-window online applications": "સિંગલ-વિન્ડો ઑનલાઇન અરજીઓ",
        "Complaint registration and status tracking": "ફરિયાદ નોંધણી અને સ્થિતિ ટ્રેકિંગ",
        "Department-wise scheme discovery": "વિભાગ મુજબ યોજના માહિતી",
        "Citizen + admin digital dashboards": "નાગરિક + એડમિન ડિજિટલ ડેશબોર્ડ",
        "Latest News": "તાજા સમાચાર",
        "View All": "બધા જુઓ",
        "Public Messages": "જાહેર સંદેશા",
        "Hon'ble Prime Minister, Government of India": "માનનીય પ્રધાનમંત્રી, ભારત સરકાર",
        "Hon'ble Chief Minister, Government of Gujarat": "માનનીય મુખ્યમંત્રી, ગુજરાત સરકાર",
        "Agriculture & Farmers Welfare Department": "કૃષિ અને ખેડૂત કલ્યાણ વિભાગ",
        "Departments & Schemes": "વિભાગો અને યોજનાઓ",
        "Krishi Vibhag Quick Access": "કૃષિ વિભાગ ઝડપી ઍક્સેસ",
        "Digital profile and service enrollment.": "ડિજિટલ પ્રોફાઇલ અને સેવા નોંધણી.",
        "Subsidy Application": "સબસિડી અરજી",
        "Department-wise subsidy workflow.": "વિભાગવાર સબસિડી પ્રક્રિયા.",
        "Irrigation Support": "સિંચાઈ સહાય",
        "Water and agriculture utility requests.": "પાણી અને કૃષિ યુટિલિટી અરજીઓ.",
        "Issue Reporting": "મુદ્દા નોંધણી",
        "File local infrastructure complaints.": "સ્થાનિક ઇન્ફ્રાસ્ટ્રક્ચર ફરિયાદ નોંધાવો.",
        "Track Status": "સ્થિતિ ટ્રેક",
        "Check digital progress in real-time.": "વાસ્તવિક સમયમાં ડિજિટલ પ્રગતિ જુઓ.",
        "Department Login": "વિભાગ લોગિન",
        "Admin panel for request processing.": "અરજી પ્રક્રિયા માટે એડમિન પેનલ.",
        "Important Videos": "મહત્વપૂર્ણ વિડિઓ",
        "More Videos": "વધુ વિડિઓ",
        "How to apply for agriculture benefits online": "કૃષિ લાભ માટે ઑનલાઇન અરજી કેવી રીતે કરવી",
        "Digital farming records and document checklist": "ડિજિટલ ખેતી રેકોર્ડ અને દસ્તાવેજ ચેકલિસ્ટ",
        "Village grievance reporting tutorial": "ગામ ફરિયાદ નોંધણી માર્ગદર્શિકા",
        "Online Services": "ઑનલાઇન સેવાઓ",
        "Apply for Panchayat Services": "પંચાયત સેવાઓ માટે અરજી કરો",
        "Submit digital applications and track status by Request ID and mobile number.": "ડિજિટલ અરજી કરો અને રિક્વેસ્ટ ID તથા મોબાઇલથી સ્થિતિ ટ્રેક કરો.",
        "Service Applications": "સેવા અરજીઓ",
        "Apply online with instant request ID.": "તાત્કાલિક રિક્વેસ્ટ ID સાથે ઑનલાઇન અરજી.",
        "Online submission and tracking.": "ઑનલાઇન સબમિશન અને ટ્રેકિંગ.",
        "Digital form-based application.": "ડિજિટલ ફોર્મ આધારિત અરજી.",
        "Add/modify/remove requests.": "ઉમેરો/સુધારો/દૂર કરવાની અરજીઓ.",
        "Utility request workflow.": "યુટિલિટી વિનંતિ પ્રક્રિયા.",
        "Status Dashboard": "સ્થિતિ ડેશબોર્ડ",
        "Track latest processing updates.": "તાજેતરના પ્રક્રિયા અપડેટ ટ્રેક કરો.",
        "Track Service Application": "સેવા અરજી ટ્રેક કરો",
        "Request ID": "રિક્વેસ્ટ ID",
        "Registered Mobile": "નોંધાયેલ મોબાઇલ",
        "Track Request": "અરજી ટ્રેક કરો",
        "Application Found": "અરજી મળી",
        "Service": "સેવા",
        "Applicant": "અરજદાર",
        "Status": "સ્થિતિ",
        "Submitted": "સબમિટ તારીખ",
        "Recent Digital Requests": "તાજેતરની ડિજિટલ અરજીઓ",
        "No requests yet.": "હજુ સુધી કોઈ અરજી નથી.",
        "Complaint Desk": "ફરિયાદ ડેસ્ક",
        "Submit and Track Village Complaints": "ગામ ફરિયાદ નોંધાવો અને ટ્રેક કરો",
        "Report civic issues and track real-time complaint status with your complaint ID.": "સિવિક સમસ્યાઓ નોંધાવો અને ફરિયાદ IDથી સ્થિતિ ટ્રેક કરો.",
        "Complaint Form": "ફરિયાદ ફોર્મ",
        "Complaint Registered": "ફરિયાદ નોંધાઈ",
        "Complaint ID": "ફરિયાદ ID",
        "Assigned Department": "સોંપાયેલ વિભાગ",
        "Full Name": "પૂરું નામ",
        "Mobile Number": "મોબાઇલ નંબર",
        "Email": "ઈમેઈલ",
        "Complaint Category": "ફરિયાદ શ્રેણી",
        "Location / Ward": "સ્થળ / વોર્ડ",
        "Complaint Details": "ફરિયાદ વિગત",
        "Submit Complaint": "ફરિયાદ નોંધાવો",
        "Track Complaint Status": "ફરિયાદ સ્થિતિ ટ્રેક કરો",
        "Check Status": "સ્થિતિ જુઓ",
        "Category": "શ્રેણી",
        "Location": "સ્થળ",
        "Department": "વિભાગ",
        "Last Updated": "છેલ્લું અપડેટ",
        "Public Notices": "જાહેર સૂચનાઓ",
        "Official Circulars and Updates": "અધિકૃત પરિપત્ર અને અપડેટ",
        "Download latest circulars and notifications issued for the village.": "ગામ માટે જાહેર થયેલ તાજા પરિપત્ર અને સૂચનાઓ ડાઉનલોડ કરો.",
        "Cleanliness Drive Guidelines": "સ્વચ્છતા અભિયાન માર્ગદર્શિકા",
        "Download PDF": "PDF ડાઉનલોડ",
        "Issued: 12 Feb 2026": "જારી: 12 ફેબ્રુઆરી 2026",
        "Village-wide cleanliness drive instructions and volunteer registration details.": "ગામવ્યાપી સ્વચ્છતા અભિયાન સૂચનાઓ અને સ્વયંસેવક નોંધણી વિગતો.",
        "Water Supply Maintenance Schedule": "પાણી પુરવઠા જાળવણી સમયપત્રક",
        "Issued: 05 Feb 2026": "જારી: 05 ફેબ્રુઆરી 2026",
        "Planned maintenance timetable and ward-wise temporary supply updates.": "યોજિત જાળવણી સમયપત્રક અને વોર્ડ મુજબ તાત્કાલિક પુરવઠા અપડેટ.",
        "Gram Sabha Meeting Circular": "ગ્રામસભા બેઠક પરિપત્ર",
        "Issued: 29 Jan 2026": "જારી: 29 જાન્યુઆરી 2026",
        "Agenda and schedule for upcoming Gram Sabha meeting.": "આગામી ગ્રામસભા બેઠક માટે એજન્ડા અને સમયપત્રક.",
        "Digital Dashboard": "ડિજિટલ ડેશબોર્ડ",
        "Live Service Monitoring": "લાઇવ સેવા મોનિટરિંગ",
        "Real-time visibility of applications, complaints, and service efficiency.": "અરજીઓ, ફરિયાદો અને સેવા કાર્યક્ષમતા માટે રિયલ-ટાઇમ નજર.",
        "Total Service Requests": "કુલ સેવા અરજીઓ",
        "Pending Requests": "બાકી અરજીઓ",
        "Recent Service Requests": "તાજેતરની સેવા અરજીઓ",
        "No complaints yet.": "હજુ સુધી કોઈ ફરિયાદ નથી.",
        "Recent Complaints": "તાજેતરની ફરિયાદો",
        "Citizen": "નાગરિક",
        "Updated": "અપડેટ",
        "About Village": "ગામ વિશે",
        "Sakhwaniya Gram Panchayat": "સખવાણિયા ગ્રામ પંચાયત",
        "Transparent governance, digital inclusion, and community-driven development.": "પારદર્શક શાસન, ડિજિટલ સમાવેશ અને સમુદાય આધારિત વિકાસ.",
        "Sakhwaniya is known for agriculture, public participation, and inclusive local planning. Gram Sabha meetings and digital processes now work together to improve service delivery.": "સખવાણિયા કૃષિ, જાહેર ભાગીદારી અને સમાન સ્થાનિક આયોજન માટે જાણીતા છે. ગ્રામસભા બેઠક અને ડિજિટલ પ્રક્રિયા હવે સાથે મળી સેવા સુધારે છે.",
        "Community-first development model": "સમુદાય-પ્રથમ વિકાસ મોડલ",
        "Digital service access for citizens": "નાગરિકો માટે ડિજિટલ સેવા પ્રવેશ",
        "Focus on sanitation, water and education": "સ્વચ્છતા, પાણી અને શિક્ષણ પર ધ્યાન",
        "Vision & Mission": "વિઝન અને મિશન",
        "Vision": "વિઝન",
        "A sustainable and empowered Sakhwaniya where every citizen thrives.": "ટકાઉ અને સશક્ત સખવાણિયા જ્યાં દરેક નાગરિક પ્રગતિ કરે.",
        "Mission": "મિશન",
        "Deliver transparent services and strengthen local infrastructure.": "પારદર્શક સેવાઓ આપવી અને સ્થાનિક ઇન્ફ્રાસ્ટ્રક્ચર મજબૂત બનાવવું.",
        "Governance": "શાસન",
        "Digital-first, accountable, and participatory Panchayat operations.": "ડિજિટલ-ફર્સ્ટ, જવાબદાર અને ભાગીદારી આધારિત પંચાયત કામગીરી.",
        "Contact Us": "અમારો સંપર્ક કરો",
        "Get in Touch": "સંપર્કમાં રહો",
        "Reach Sakhwaniya Gram Panchayat office for support and queries.": "મદદ અને માહિતી માટે સખવાણિયા ગ્રામ પંચાયત કચેરીનો સંપર્ક કરો.",
        "Office Address": "કચેરીનું સરનામું",
        "Phone": "ફોન",
        "Office Hours": "કાર્ય સમય",
        "Account Access": "એકાઉન્ટ ઍક્સેસ",
        "Citizen Login": "નાગરિક લોગિન",
        "Admin Login": "એડમિન લોગિન",
        "Login to access your profile, track requests, and use digital services.": "તમારી પ્રોફાઇલ, અરજી ટ્રેકિંગ અને ડિજિટલ સેવાઓ માટે લોગિન કરો.",
        "Login with admin or staff credentials to open the digital operations panel.": "ડિજિટલ ઑપરેશન્સ પેનલ ખોલવા માટે એડમિન અથવા સ્ટાફ વિગતો સાથે લોગિન કરો.",
        "Password": "પાસવર્ડ",
        "Enter registered mobile number": "નોંધાયેલ મોબાઇલ નંબર દાખલ કરો",
        "Enter password": "પાસવર્ડ દાખલ કરો",
        "Don't have an account?": "એકાઉન્ટ નથી?",
        "Create account": "એકાઉન્ટ બનાવો",
        "Citizen Registration": "નાગરિક નોંધણી",
        "Create your account and start using GramSetu online services.": "તમારું એકાઉન્ટ બનાવો અને ગ્રામસેતુ ઑનલાઇન સેવાઓનો ઉપયોગ શરૂ કરો.",
        "Enter full name": "પૂરું નામ દાખલ કરો",
        "Enter mobile number": "મોબાઇલ નંબર દાખલ કરો",
        "Email (Optional)": "ઈમેઈલ (વૈકલ્પિક)",
        "Enter email address": "ઈમેઈલ સરનામું દાખલ કરો",
        "Create password": "પાસવર્ડ બનાવો",
        "Confirm Password": "પાસવર્ડ ખાતરી",
        "Re-enter password": "પાસવર્ડ ફરી દાખલ કરો",
        "Create Account": "એકાઉન્ટ બનાવો",
        "Already registered?": "પહેલેથી નોંધાયેલ છો?",
        "Login here": "અહીં લોગિન કરો",
        "Birth Certificate Application": "જન્મ પ્રમાણપત્ર અરજી",
        "Income Certificate Application": "આવક પ્રમાણપત્ર અરજી",
        "Caste Certificate Application": "જાતિ પ્રમાણપત્ર અરજી",
        "Ration Card Update Request": "રેશન કાર્ડ અપડેટ અરજી",
        "Water Connection Request": "પાણી કનેક્શન અરજી",
        "Service Application": "સેવા અરજી",
        "Fill in details to generate your digital request ID.": "તમારી ડિજિટલ રિક્વેસ્ટ ID બનાવવા માટે વિગતો ભરો.",
        "Application Submitted": "અરજી સબમિટ થઈ",
        "Track This Application": "આ અરજી ટ્રેક કરો",
        "Applicant Name": "અરજદાર નામ",
        "Child Name": "બાળકનું નામ",
        "Date of Birth": "જન્મ તારીખ",
        "Father Name": "પિતાનું નામ",
        "Mother Name": "માતાનું નામ",
        "Address": "સરનામું",
        "Submit Application": "અરજી સબમિટ કરો",
        "Father/Guardian Name": "પિતા/વાલીનું નામ",
        "Annual Income": "વાર્ષિક આવક",
        "Income Source": "આવક સ્ત્રોત",
        "Caste/Community": "જાતિ/સમુદાય",
        "Request Submitted": "વિનંતી સબમિટ થઈ",
        "Track This Request": "આ વિનંતી ટ્રેક કરો",
        "Head of Family": "કુટુંબના વડા",
        "Ration Card Number": "રેશન કાર્ડ નંબર",
        "Update Type": "અપડેટ પ્રકાર",
        "Add / Remove / Modify": "ઉમેરો / દૂર કરો / સુધારો",
        "Submit Request": "વિનંતી સબમિટ કરો",
        "Purpose": "હેતુ",
        "Enter both Request ID and mobile number to track your application.": "અરજી ટ્રેક કરવા માટે રિક્વેસ્ટ ID અને મોબાઇલ નંબર બંને દાખલ કરો.",
        "No application found. Check your Request ID and mobile number.": "કોઈ અરજી મળી નથી. કૃપા કરીને રિક્વેસ્ટ ID અને મોબાઇલ નંબર તપાસો.",
        "Enter both Complaint ID and mobile number to track your complaint.": "ફરિયાદ ટ્રેક કરવા માટે ફરિયાદ ID અને મોબાઇલ નંબર બંને દાખલ કરો.",
        "No complaint found. Check your Complaint ID and mobile number.": "કોઈ ફરિયાદ મળી નથી. કૃપા કરીને ફરિયાદ ID અને મોબાઇલ નંબર તપાસો.",
        "Full name is required.": "પૂરું નામ જરૂરી છે.",
        "Applicant name is required.": "અરજદારનું નામ જરૂરી છે.",
        "Mobile number is required.": "મોબાઇલ નંબર જરૂરી છે.",
        "Complaint category is required.": "ફરિયાદ શ્રેણી જરૂરી છે.",
        "Location is required.": "સ્થળ જરૂરી છે.",
        "Complaint details are required.": "ફરિયાદ વિગત જરૂરી છે.",
        "Password is required.": "પાસવર્ડ જરૂરી છે.",
        "Password must be at least 6 characters.": "પાસવર્ડ ઓછામાં ઓછા 6 અક્ષરનો હોવો જોઈએ.",
        "Password and confirm password do not match.": "પાસવર્ડ અને કન્ફર્મ પાસવર્ડ સરખા નથી.",
        "Registration successful. Please login.": "નોંધણી સફળ. કૃપા કરીને લોગિન કરો.",
        "Mobile number or email already registered. Try logging in.": "મોબાઇલ નંબર અથવા ઈમેઈલ પહેલેથી નોંધાયેલ છે. કૃપા કરીને લોગિન કરો.",
        "Enter mobile number and password.": "મોબાઇલ નંબર અને પાસવર્ડ દાખલ કરો.",
        "Invalid login credentials.": "લોગિન માહિતી અમાન્ય છે.",
        "Only admin or staff accounts can access the admin panel.": "ફક્ત એડમિન અથવા સ્ટાફ એકાઉન્ટને એડમિન પેનલ પ્રવેશ છે.",
        "You are signed in as {full_name}. Logging in here will switch to an admin or staff account.": "તમે હાલમાં {full_name} તરીકે સાઇન ઇન છો. અહીં લોગિન કરવાથી એડમિન અથવા સ્ટાફ એકાઉન્ટમાં સ્વિચ થશે.",
        "Need a citizen account instead?": "નાગરિક એકાઉન્ટમાં જવું છે?",
        "Go to citizen login": "નાગરિક લોગિન પર જાઓ",
        "Login to Admin Panel": "એડમિન પેનલમાં લોગિન કરો",
        "Could not save service request.": "સેવા અરજી સંગ્રહિત કરી શકાઈ નથી.",
        "Could not save complaint.": "ફરિયાદ સંગ્રહિત કરી શકાઈ નથી.",
        "Could not generate a unique request ID. Please retry.": "અનન્ય રિક્વેસ્ટ ID બની શકી નથી. ફરી પ્રયાસ કરો.",
        "Could not generate a unique complaint ID. Please retry.": "અનન્ય ફરિયાદ ID બની શકી નથી. ફરી પ્રયાસ કરો.",
        "About - GramSetu": "પરિચય - ગ્રામસેતુ",
        "Admin - GramSetu": "એડમિન - ગ્રામસેતુ",
        "Applications": "અરજીઓ",
        "Birth Certificate": "જન્મ પ્રમાણપત્ર",
        "Birth Certificate - GramSetu": "જન્મ પ્રમાણપત્ર - ગ્રામસેતુ",
        "Caste Certificate": "જાતિ પ્રમાણપત્ર",
        "Caste Certificate - GramSetu": "જાતિ પ્રમાણપત્ર - ગ્રામસેતુ",
        "Citizen Site": "નાગરિક વેબસાઇટ",
        "Complaint Status": "ફરિયાદ સ્થિતિ",
        "Complaints - GramSetu": "ફરિયાદો - ગ્રામસેતુ",
        "Contact - GramSetu": "સંપર્ક - ગ્રામસેતુ",
        "Digital Dashboard - GramSetu": "ડિજિટલ ડેશબોર્ડ - ગ્રામસેતુ",
        "Digital Operations Panel": "ડિજિટલ ઑપરેશન્સ પેનલ",
        "Digital complaint response timeline reduced for priority cases.": "પ્રાથમિક કેસો માટે ડિજિટલ ફરિયાદ પ્રતિસાદ સમયરેખા ઘટાડવામાં આવી.",
        "Farm field": "ખેતર",
        "Farmer support camp schedule published in notices section.": "ખેડૂત સહાય કેમ્પનું સમયપત્રક જાહેર સૂચનાઓ વિભાગમાં પ્રકાશિત થયું.",
        "Gram Sabha circular uploaded with village development agenda.": "ગામ વિકાસ એજન્ડા સાથે ગ્રામસભાનો પરિપત્ર અપલોડ થયો.",
        "GramSetu - iKhedut Style Portal": "ગ્રામસેતુ - iKhedut શૈલી પોર્ટલ",
        "GramSetu Admin": "ગ્રામસેતુ એડમિન",
        "Income Certificate": "આવક પ્રમાણપત્ર",
        "Income Certificate - GramSetu": "આવક પ્રમાણપત્ર - ગ્રામસેતુ",
        "Invalid user role.": "અમાન્ય યુઝર ભૂમિકા.",
        "Login - GramSetu": "લોગિન - ગ્રામસેતુ",
        "Mon-Sat, 10:00 AM - 5:00 PM": "સોમ-શનિ, સવારે 10:00 થી સાંજે 5:00",
        "New cycle for water connection online requests has started.": "પાણી કનેક્શન માટે ઑનલાઇન અરજીઓનો નવો ચક્ર શરૂ થયો છે.",
        "Notices - GramSetu": "જાહેર સૂચનાઓ - ગ્રામસેતુ",
        "Online Services - GramSetu": "ઑનલાઇન સેવાઓ - ગ્રામસેતુ",
        "Ration Card Update": "રેશન કાર્ડ અપડેટ",
        "Ration Card Update - GramSetu": "રેશન કાર્ડ અપડેટ - ગ્રામસેતુ",
        "Register - GramSetu": "રજીસ્ટર - ગ્રામસેતુ",
        "SRV-20260415-XXXXXX": "SRV-20260415-XXXXXX",
        "Sakhwaniya Gram Panchayat Map": "સખવાણિયા ગ્રામ પંચાયત નકશો",
        "Users": "યુઝર્સ",
        "Video 1": "વિડિઓ 1",
        "Video 2": "વિડિઓ 2",
        "Video 3": "વિડિઓ 3",
        "Village": "ગામ",
        "Water Connection": "પાણી કનેક્શન",
        "Water Connection - GramSetu": "પાણી કનેક્શન - ગ્રામસેતુ",
        "05 Apr 2026:": "05 એપ્રિલ 2026:",
        "09 Apr 2026:": "09 એપ્રિલ 2026:",
        "12 Apr 2026:": "12 એપ્રિલ 2026:",
        "15 Apr 2026:": "15 એપ્રિલ 2026:",
    }
}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _normalize_mobile(mobile: str) -> str:
    cleaned = _clean(mobile)
    if not cleaned:
        return ""
    # Remove any non-digit characters
    digits = re.sub(r'\D', '', cleaned)
    # If 10 digits, assume Indian, add +91
    if len(digits) == 10:
        return f"+91{digits}"
    # If starts with 91 and 12 digits, add +
    if len(digits) == 12 and digits.startswith('91'):
        return f"+{digits}"
    # If already has +, return as is
    if cleaned.startswith('+'):
        return cleaned
    # Otherwise, assume it's already international
    return f"+{digits}"


def get_current_language() -> str:
    if not has_request_context():
        return DEFAULT_LANGUAGE
    current = _clean(str(session.get("lang", DEFAULT_LANGUAGE))).lower()
    if current in SUPPORTED_LANGUAGES:
        return current
    return DEFAULT_LANGUAGE


def _translate(text: str, **kwargs) -> str:
    language = get_current_language()
    translated = TEXT_TRANSLATIONS.get(language, {}).get(text, text)
    if kwargs:
        try:
            return translated.format(**kwargs)
        except KeyError:
            return translated
    return translated


def _status_label(status: str) -> str:
    labels = STATUS_LABELS.get(status)
    if not labels:
        return status.replace("_", " ").title()
    return labels.get(get_current_language(), labels["en"])


def _generate_token(prefix: str) -> str:
    return f"{prefix}-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _clean(value).lower()).strip("-")
    return slug


def _normalize_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", _clean(value).lower()).strip("_")


def _coerce_checkbox(value: str | None) -> bool:
    return _clean(value).lower() in {"1", "true", "yes", "on"}


def _parse_date_input(
    value: str | None, *, field_label: str = "Date", required: bool = False
):
    cleaned = _clean(value)
    if not cleaned:
        if required:
            raise ValueError(f"{field_label} is required.")
        return None

    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid {field_label.lower()}. Use YYYY-MM-DD format.") from exc


def _parse_form_fields_config(raw_json: str | None) -> list[dict]:
    cleaned = _clean(raw_json)
    if not cleaned:
        raise ValueError("Form field JSON is required.")

    try:
        config = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Form field JSON must be valid JSON.") from exc

    if not isinstance(config, list) or not config:
        raise ValueError("Form field JSON must be a non-empty array.")

    normalized_fields: list[dict] = []
    used_names: set[str] = set()

    for index, field in enumerate(config, start=1):
        if not isinstance(field, dict):
            raise ValueError(f"Field #{index} must be an object.")

        name = _normalize_field_name(str(field.get("name", "")))
        label = _clean(str(field.get("label", "")))
        field_type = _clean(str(field.get("type", "text"))).lower()
        placeholder = _clean(str(field.get("placeholder", "")))
        help_text = _clean(str(field.get("help_text", "")))
        required = bool(field.get("required"))

        if not re.fullmatch(r"[a-z][a-z0-9_]{1,49}", name):
            raise ValueError(
                f"Field #{index} needs a valid name using lowercase letters, numbers, and underscore."
            )
        if name in used_names:
            raise ValueError(f"Field name '{name}' is duplicated.")
        if name in RESERVED_DYNAMIC_FIELD_NAMES:
            raise ValueError(
                f"Field name '{name}' is reserved because applicant contact fields are added automatically."
            )
        if not label:
            raise ValueError(f"Field #{index} label is required.")
        if field_type not in FORM_FIELD_TYPES:
            raise ValueError(
                f"Field '{name}' type must be one of: {', '.join(FORM_FIELD_TYPES)}."
            )

        normalized_field = {
            "name": name,
            "label": label,
            "type": field_type,
            "required": required,
            "placeholder": placeholder,
            "help_text": help_text,
        }

        if field_type == "select":
            raw_options = field.get("options")
            if not isinstance(raw_options, list) or not raw_options:
                raise ValueError(f"Field '{name}' must include a non-empty options array.")

            options = [_clean(str(option)) for option in raw_options if _clean(str(option))]
            if not options:
                raise ValueError(f"Field '{name}' must include valid select options.")
            normalized_field["options"] = options

        normalized_fields.append(normalized_field)
        used_names.add(name)

    return normalized_fields


def _upload_root() -> str:
    configured_root = _clean(app.config.get("UPLOAD_FOLDER"))
    if configured_root:
        return os.path.abspath(configured_root)
    return os.path.join(os.path.dirname(__file__), "uploads")


def _ensure_upload_root() -> None:
    os.makedirs(_upload_root(), exist_ok=True)


def _is_allowed_upload(filename: str) -> bool:
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in set(app.config["ALLOWED_UPLOAD_EXTENSIONS"])


def _normalize_uploaded_items(files, allowed_field_names: set[str] | None = None) -> list[dict]:
    if not files:
        return []

    normalized: list[dict] = []
    field_names = allowed_field_names or set(files.keys())
    for field_name in field_names:
        for item in files.getlist(field_name):
            filename = _clean(getattr(item, "filename", ""))
            if not filename:
                continue
            if not _is_allowed_upload(filename):
                raise ValueError(
                    "Unsupported file type. Allowed formats: "
                    + ", ".join(app.config["ALLOWED_UPLOAD_EXTENSIONS"])
                )
            normalized.append({"field_name": field_name, "file": item})
    return normalized


def _validate_dynamic_service_submission(fields: list[dict], form_data, files) -> None:
    uploaded_groups = {}
    for item in _normalize_uploaded_items(files):
        uploaded_groups.setdefault(item["field_name"], []).append(item)

    for field in fields:
        if field["type"] == "file":
            if field["required"] and not uploaded_groups.get(field["name"]):
                raise ValueError(f"{field['label']} is required.")
            continue

        value = _clean(form_data.get(field["name"]))
        if field["required"] and not value:
            raise ValueError(f"{field['label']} is required.")
        if field["type"] == "select" and value and value not in field.get("options", []):
            raise ValueError(f"Invalid value selected for {field['label']}.")


def _extract_openai_text(payload: dict) -> str:
    output_text = _clean(payload.get("output_text"))
    if output_text:
        return output_text

    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
            elif content.get("type") == "text":
                text_block = content.get("text")
                if isinstance(text_block, dict):
                    chunks.append(text_block.get("value", ""))
                else:
                    chunks.append(str(text_block or ""))
    return "\n".join(chunk for chunk in chunks if _clean(chunk))


def _request_next_path() -> str:
    if request.query_string:
        value = request.full_path
        return value[:-1] if value.endswith("?") else value
    return request.path


def _is_safe_next(next_url: str | None) -> bool:
    if not next_url:
        return False
    return next_url.startswith("/") and not next_url.startswith("//")


def _mysql_connection_kwargs(
    include_db: bool = True, autocommit: bool = False
) -> dict:
    kwargs = {
        "host": app.config["MYSQL_HOST"],
        "port": app.config["MYSQL_PORT"],
        "user": app.config["MYSQL_USER"],
        "password": app.config["MYSQL_PASSWORD"],
        "charset": app.config["MYSQL_CHARSET"],
        "cursorclass": DictCursor,
        "autocommit": autocommit,
    }
    if include_db:
        kwargs["database"] = app.config["MYSQL_DB"]
    return kwargs


def get_db() -> pymysql.connections.Connection:
    if "db" not in g:
        g.db = pymysql.connect(
            **_mysql_connection_kwargs(include_db=True, autocommit=False)
        )
    return g.db


@app.before_request
def ensure_language() -> None:
    language = _clean(str(session.get("lang", DEFAULT_LANGUAGE))).lower()
    if language not in SUPPORTED_LANGUAGES:
        session["lang"] = DEFAULT_LANGUAGE


@app.teardown_appcontext
def close_db(_error: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        if _error is not None:
            db.rollback()
        db.close()


def _validate_database_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("MYSQL_DB must contain only letters, numbers, and underscore.")
    return name


def init_db() -> None:
    db_name = _validate_database_name(app.config["MYSQL_DB"])

    server_conn = pymysql.connect(
        **_mysql_connection_kwargs(include_db=False, autocommit=True)
    )
    try:
        with server_conn.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS `{db_name}`
                CHARACTER SET utf8mb4
                COLLATE utf8mb4_unicode_ci
                """
            )
    finally:
        server_conn.close()

    db = get_db()
    table_statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          full_name VARCHAR(150) NOT NULL,
          mobile VARCHAR(20) NOT NULL UNIQUE,
          email VARCHAR(150) NULL UNIQUE,
          password_hash VARCHAR(255) NOT NULL,
          role ENUM('citizen','admin','staff') NOT NULL DEFAULT 'citizen',
          status ENUM('active','inactive') NOT NULL DEFAULT 'active',
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX idx_users_role (role)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS service_requests (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          request_id VARCHAR(50) NOT NULL UNIQUE,
          service_code VARCHAR(50) NOT NULL,
          applicant_name VARCHAR(150) NOT NULL,
          mobile VARCHAR(20) NOT NULL,
          email VARCHAR(150) NULL,
          details_json JSON NULL,
          status ENUM('submitted','under_review','approved','rejected')
            NOT NULL DEFAULT 'submitted',
          submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX idx_service_requests_mobile (mobile)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS complaints (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          complaint_id VARCHAR(50) NOT NULL UNIQUE,
          full_name VARCHAR(150) NOT NULL,
          mobile VARCHAR(20) NOT NULL,
          email VARCHAR(150) NULL,
          category VARCHAR(100) NOT NULL,
          location VARCHAR(150) NOT NULL,
          details TEXT NOT NULL,
          status ENUM('open','in_progress','resolved','closed')
            NOT NULL DEFAULT 'open',
          assigned_department VARCHAR(100) NOT NULL DEFAULT 'General',
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX idx_complaints_mobile (mobile)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS notices (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          title VARCHAR(180) NOT NULL,
          reference_no VARCHAR(80) NULL,
          summary TEXT NOT NULL,
          body TEXT NULL,
          issued_on DATE NOT NULL,
          download_url VARCHAR(255) NULL,
          is_published TINYINT(1) NOT NULL DEFAULT 1,
          created_by_user_id BIGINT UNSIGNED NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX idx_notices_published (is_published, issued_on)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS service_catalog (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          code VARCHAR(80) NOT NULL UNIQUE,
          slug VARCHAR(120) NOT NULL UNIQUE,
          title VARCHAR(180) NOT NULL,
          department VARCHAR(120) NOT NULL DEFAULT 'Gram Panchayat',
          category VARCHAR(120) NOT NULL DEFAULT 'Citizen Service',
          summary TEXT NOT NULL,
          intro TEXT NULL,
          eligibility TEXT NULL,
          documents TEXT NULL,
          instructions TEXT NULL,
          fields_json JSON NOT NULL,
          is_published TINYINT(1) NOT NULL DEFAULT 1,
          created_by_user_id BIGINT UNSIGNED NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX idx_service_catalog_published (is_published, updated_at),
          INDEX idx_service_catalog_category (category)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS uploaded_documents (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          entity_type VARCHAR(40) NOT NULL,
          entity_ref VARCHAR(50) NOT NULL,
          field_name VARCHAR(80) NOT NULL DEFAULT 'supporting_documents',
          original_name VARCHAR(255) NOT NULL,
          stored_name VARCHAR(255) NOT NULL,
          stored_path VARCHAR(255) NOT NULL,
          mime_type VARCHAR(150) NULL,
          file_size BIGINT UNSIGNED NOT NULL DEFAULT 0,
          uploaded_by_mobile VARCHAR(20) NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_uploaded_documents_entity (entity_type, entity_ref)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS notification_logs (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          entity_type VARCHAR(40) NULL,
          entity_ref VARCHAR(50) NULL,
          event_code VARCHAR(80) NOT NULL,
          channel VARCHAR(20) NOT NULL,
          recipient VARCHAR(180) NOT NULL,
          subject VARCHAR(255) NULL,
          message_text TEXT NOT NULL,
          status VARCHAR(20) NOT NULL,
          error_text TEXT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_notification_logs_entity (entity_type, entity_ref),
          INDEX idx_notification_logs_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    ]

    with db.cursor() as cursor:
        for statement in table_statements:
            cursor.execute(statement)
    db.commit()
    _ensure_upload_root()

    default_admin_mobile = _clean(os.getenv("DEFAULT_ADMIN_MOBILE"))
    default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    default_admin_name = _clean(os.getenv("DEFAULT_ADMIN_NAME")) or "System Admin"
    default_admin_email = _clean(os.getenv("DEFAULT_ADMIN_EMAIL")) or None
    if default_admin_mobile and default_admin_password:
        _ensure_default_admin(
            full_name=default_admin_name,
            mobile=default_admin_mobile,
            email=default_admin_email,
            password=default_admin_password,
        )


def _service_name(service_code: str) -> str:
    labels = SERVICE_LABELS.get(service_code)
    if labels:
        language = get_current_language()
        return labels.get(language, labels["en"])

    service_titles = getattr(g, "service_catalog_titles", None)
    if service_titles is None:
        rows = _fetch_all("SELECT code, title FROM service_catalog")
        service_titles = {row["code"]: row["title"] for row in rows}
        g.service_catalog_titles = service_titles
    return service_titles.get(service_code, service_code.replace("_", " ").title())


def _row_to_service_request(row: dict | None) -> dict | None:
    if row is None:
        return None

    details = {}
    raw_details = row.get("details_json")
    if raw_details:
        if isinstance(raw_details, (dict, list)):
            details = raw_details
        else:
            try:
                details = json.loads(raw_details)
            except (json.JSONDecodeError, TypeError):
                details = {}

    return {
        "request_id": row["request_id"],
        "service_code": row["service_code"],
        "service_name": _service_name(row["service_code"]),
        "applicant_name": row["applicant_name"],
        "mobile": row["mobile"],
        "email": row["email"],
        "status": row["status"],
        "submitted_at": row["submitted_at"],
        "updated_at": row["updated_at"],
        "details": details,
    }


def _row_to_notice(row: dict | None) -> dict | None:
    if row is None:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "reference_no": row["reference_no"],
        "summary": row["summary"],
        "body": row["body"],
        "issued_on": row["issued_on"],
        "download_url": row["download_url"],
        "is_published": bool(row["is_published"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_service_catalog(row: dict | None) -> dict | None:
    if row is None:
        return None

    fields: list[dict] = []
    raw_fields = row.get("fields_json")
    if raw_fields:
        if isinstance(raw_fields, list):
            fields = raw_fields
        else:
            try:
                fields = json.loads(raw_fields)
            except (json.JSONDecodeError, TypeError):
                fields = []

    return {
        "id": row["id"],
        "code": row["code"],
        "slug": row["slug"],
        "title": row["title"],
        "department": row["department"],
        "category": row["category"],
        "summary": row["summary"],
        "intro": row["intro"],
        "eligibility": row["eligibility"],
        "documents": row["documents"],
        "instructions": row["instructions"],
        "fields": fields,
        "fields_json_text": json.dumps(fields, indent=2),
        "is_published": bool(row["is_published"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_complaint(row: dict | None) -> dict | None:
    if row is None:
        return None

    return {
        "complaint_id": row["complaint_id"],
        "full_name": row["full_name"],
        "mobile": row["mobile"],
        "email": row["email"],
        "category": row["category"],
        "location": row["location"],
        "details": row["details"],
        "status": row["status"],
        "assigned_department": row["assigned_department"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_uploaded_document(row: dict | None) -> dict | None:
    if row is None:
        return None

    return {
        "id": row["id"],
        "entity_type": row["entity_type"],
        "entity_ref": row["entity_ref"],
        "field_name": row["field_name"],
        "original_name": row["original_name"],
        "stored_name": row["stored_name"],
        "stored_path": row["stored_path"],
        "mime_type": row["mime_type"],
        "file_size": int(row["file_size"] or 0),
        "uploaded_by_mobile": row["uploaded_by_mobile"],
        "created_at": row["created_at"],
    }


def _row_to_notification_log(row: dict | None) -> dict | None:
    if row is None:
        return None

    return {
        "id": row["id"],
        "entity_type": row["entity_type"],
        "entity_ref": row["entity_ref"],
        "event_code": row["event_code"],
        "channel": row["channel"],
        "recipient": row["recipient"],
        "subject": row["subject"],
        "message_text": row["message_text"],
        "status": row["status"],
        "error_text": row["error_text"],
        "created_at": row["created_at"],
    }


def _user_public_payload(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "mobile": row["mobile"],
        "email": row["email"],
        "role": row["role"],
        "status": row["status"],
    }


def _get_user_by_id(user_id: int | str | None) -> dict | None:
    if not user_id:
        return None
    return _fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))


def _get_user_by_mobile(mobile: str) -> dict | None:
    return _fetch_one("SELECT * FROM users WHERE mobile = %s", (_clean(mobile),))


def _get_user_by_email(email: str | None) -> dict | None:
    cleaned_email = _clean(email)
    if not cleaned_email:
        return None
    return _fetch_one("SELECT * FROM users WHERE email = %s", (cleaned_email,))


def _insert_user(
    *, full_name: str, mobile: str, email: str | None, password: str, role: str = "citizen"
) -> int:
    if role not in USER_ROLE_OPTIONS:
        raise ValueError(_translate("Invalid user role."))
    if len(password) < 6:
        raise ValueError(_translate("Password must be at least 6 characters."))

    password_hash = generate_password_hash(password)
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users (full_name, mobile, email, password_hash, role, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
            """,
            (_clean(full_name), _clean(mobile), email, password_hash, role),
        )
        user_id = cursor.lastrowid
    db.commit()
    return int(user_id)


def _ensure_default_admin(
    *, full_name: str, mobile: str, email: str | None, password: str
) -> None:
    cleaned_mobile = _clean(mobile)
    cleaned_email = _clean(email) or None
    existing = _get_user_by_mobile(cleaned_mobile) or _get_user_by_email(cleaned_email)
    if existing:
        resolved_email = cleaned_email
        email_owner = _get_user_by_email(cleaned_email)
        if email_owner and email_owner["id"] != existing["id"]:
            resolved_email = existing["email"]
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET full_name = %s,
                    mobile = %s,
                    email = %s,
                    password_hash = %s,
                    role = 'admin',
                    status = 'active'
                WHERE id = %s
                """,
                (
                    _clean(full_name),
                    cleaned_mobile,
                    resolved_email,
                    generate_password_hash(password),
                    existing["id"],
                ),
            )
        db.commit()
        return
    try:
        _insert_user(
            full_name=full_name,
            mobile=cleaned_mobile,
            email=cleaned_email,
            password=password,
            role="admin",
        )
    except (IntegrityError, ValueError):
        get_db().rollback()


def get_current_user() -> dict | None:
    if "auth_user" in g:
        return g.auth_user

    user_id = session.get("user_id")
    if not user_id:
        g.auth_user = None
        return None

    row = _get_user_by_id(user_id)
    user = _user_public_payload(row)
    if not user or user["status"] != "active":
        selected_language = get_current_language()
        session.clear()
        session["lang"] = selected_language
        g.auth_user = None
        return None

    g.auth_user = user
    return user


def _login_user(user_row: dict) -> None:
    session["user_id"] = int(user_row["id"])


def _logout_user() -> None:
    selected_language = get_current_language()
    session.clear()
    session["lang"] = selected_language


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("login", next=_request_next_path()))
        return view(*args, **kwargs)

    return wrapped_view


def role_required(*roles: str):
    allowed = set(roles)

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = get_current_user()
            login_endpoint = "admin_login" if request.path.startswith("/admin") else "login"
            if user is None:
                return redirect(url_for(login_endpoint, next=_request_next_path()))
            if user["role"] not in allowed:
                return redirect(url_for(login_endpoint, next=_request_next_path()))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


@app.context_processor
def inject_auth_user():
    return {
        "auth_user": get_current_user(),
        "lang": get_current_language(),
        "t": _translate,
        "status_text": _status_label,
        "current_path": _request_next_path(),
    }


def _fetch_one(query: str, params: tuple = ()) -> dict | None:
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def _normalize_limit(limit: int) -> int:
    return max(1, min(int(limit), 500))


def list_users(limit: int = 200) -> list[dict]:
    limit = _normalize_limit(limit)
    rows = _fetch_all(
        f"""
        SELECT * FROM users
        ORDER BY created_at DESC
        LIMIT {limit}
        """
    )
    return [_user_public_payload(row) for row in rows]


def create_admin_managed_user(form_data: dict) -> dict:
    full_name = _clean(form_data.get("full_name"))
    mobile = _clean(form_data.get("mobile"))
    email = _clean(form_data.get("email")) or None
    password = form_data.get("password", "")
    role = _clean(form_data.get("role")) or "citizen"
    status = _clean(form_data.get("status")) or "active"

    if not full_name:
        raise ValueError("Full name is required.")
    if not mobile:
        raise ValueError("Mobile number is required.")
    if role not in USER_ROLE_OPTIONS:
        raise ValueError("Invalid user role.")
    if status not in USER_STATUS_OPTIONS:
        raise ValueError("Invalid user status.")

    try:
        user_id = _insert_user(
            full_name=full_name,
            mobile=mobile,
            email=email,
            password=password,
            role=role,
        )
        if status != "active":
            db = get_db()
            with db.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (status, user_id),
                )
            db.commit()
    except IntegrityError as exc:
        get_db().rollback()
        raise ValueError("Mobile number or email already registered.") from exc

    return _user_public_payload(_get_user_by_id(user_id))


def update_user_admin_access(
    user_id: str | int | None,
    *,
    role: str,
    status: str,
    current_user_id: int | None = None,
) -> bool:
    target_user = _get_user_by_id(user_id)
    if target_user is None:
        raise ValueError("User was not found.")
    if role not in USER_ROLE_OPTIONS:
        raise ValueError("Invalid user role.")
    if status not in USER_STATUS_OPTIONS:
        raise ValueError("Invalid user status.")

    current_user_id = int(current_user_id) if current_user_id else None
    if current_user_id and int(target_user["id"]) == current_user_id:
        if status != "active":
            raise ValueError("You cannot deactivate your own account.")
        if role not in ADMIN_ROLE_OPTIONS:
            raise ValueError("You cannot remove your own admin access.")

    removing_admin_access = target_user["role"] in ADMIN_ROLE_OPTIONS and (
        role not in ADMIN_ROLE_OPTIONS or status != "active"
    )
    if removing_admin_access:
        active_admins = _count(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role IN ('admin', 'staff') AND status = 'active'
            """
        )
        if active_admins <= 1:
            raise ValueError("At least one active admin or staff account must remain.")

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET role = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (role, status, target_user["id"]),
        )
        changed = cursor.rowcount
    db.commit()
    return changed > 0


def get_service_request_by_request_id(request_id: str | None) -> dict | None:
    cleaned_request_id = _clean(request_id)
    if not cleaned_request_id:
        return None
    row = _fetch_one(
        "SELECT * FROM service_requests WHERE request_id = %s", (cleaned_request_id,)
    )
    item = _row_to_service_request(row)
    if item:
        item["documents"] = list_uploaded_documents("service_request", item["request_id"])
        item["document_count"] = len(item["documents"])
    return item


def get_complaint_by_id(complaint_id: str | None) -> dict | None:
    cleaned_complaint_id = _clean(complaint_id)
    if not cleaned_complaint_id:
        return None
    row = _fetch_one(
        "SELECT * FROM complaints WHERE complaint_id = %s", (cleaned_complaint_id,)
    )
    item = _row_to_complaint(row)
    if item:
        item["documents"] = list_uploaded_documents("complaint", item["complaint_id"])
        item["document_count"] = len(item["documents"])
    return item


def _cleanup_saved_uploads(saved_paths: list[str]) -> None:
    for path in saved_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            continue


def _save_uploaded_documents(
    entity_type: str,
    entity_ref: str,
    uploaded_items: list[dict],
    *,
    uploaded_by_mobile: str | None = None,
) -> list[dict]:
    if not uploaded_items:
        return []

    _ensure_upload_root()
    saved_paths: list[str] = []
    documents: list[dict] = []
    db = get_db()

    try:
        with db.cursor() as cursor:
            for item in uploaded_items:
                file_obj = item["file"]
                original_name = _clean(getattr(file_obj, "filename", "")) or "document"
                safe_name = secure_filename(original_name) or f"document-{uuid4().hex[:8]}"
                relative_dir = os.path.join(
                    entity_type,
                    datetime.now().strftime("%Y"),
                    datetime.now().strftime("%m"),
                    _clean(entity_ref),
                )
                absolute_dir = os.path.join(_upload_root(), relative_dir)
                os.makedirs(absolute_dir, exist_ok=True)

                stored_name = f"{uuid4().hex[:12]}-{safe_name}"
                absolute_path = os.path.join(absolute_dir, stored_name)
                file_obj.save(absolute_path)
                saved_paths.append(absolute_path)

                relative_path = os.path.relpath(absolute_path, _upload_root())
                mime_type = file_obj.mimetype or mimetypes.guess_type(original_name)[0]
                file_size = os.path.getsize(absolute_path)

                cursor.execute(
                    """
                    INSERT INTO uploaded_documents
                    (
                        entity_type, entity_ref, field_name, original_name,
                        stored_name, stored_path, mime_type, file_size, uploaded_by_mobile
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entity_type,
                        entity_ref,
                        item["field_name"],
                        original_name,
                        stored_name,
                        relative_path,
                        mime_type,
                        file_size,
                        _clean(uploaded_by_mobile) or None,
                    ),
                )
                documents.append(
                    {
                        "id": cursor.lastrowid,
                        "entity_type": entity_type,
                        "entity_ref": entity_ref,
                        "field_name": item["field_name"],
                        "original_name": original_name,
                        "stored_name": stored_name,
                        "stored_path": relative_path,
                        "mime_type": mime_type,
                        "file_size": file_size,
                        "uploaded_by_mobile": _clean(uploaded_by_mobile) or None,
                    }
                )
    except Exception:
        _cleanup_saved_uploads(saved_paths)
        raise

    return documents


def list_uploaded_documents(entity_type: str, entity_ref: str) -> list[dict]:
    if not entity_ref:
        return []
    rows = _fetch_all(
        """
        SELECT * FROM uploaded_documents
        WHERE entity_type = %s AND entity_ref = %s
        ORDER BY created_at ASC
        """,
        (entity_type, entity_ref),
    )
    return [_row_to_uploaded_document(row) for row in rows]


def get_uploaded_document_by_id(document_id: str | int | None) -> dict | None:
    if not document_id:
        return None
    row = _fetch_one("SELECT * FROM uploaded_documents WHERE id = %s", (document_id,))
    return _row_to_uploaded_document(row)


def _attach_documents_to_records(items: list[dict], *, entity_type: str, ref_key: str) -> list[dict]:
    if not items:
        return items

    refs = [_clean(item.get(ref_key)) for item in items if _clean(item.get(ref_key))]
    if not refs:
        for item in items:
            item["documents"] = []
            item["document_count"] = 0
        return items

    placeholders = ", ".join(["%s"] * len(refs))
    rows = _fetch_all(
        f"""
        SELECT * FROM uploaded_documents
        WHERE entity_type = %s AND entity_ref IN ({placeholders})
        ORDER BY created_at ASC
        """,
        tuple([entity_type, *refs]),
    )
    by_ref: dict[str, list[dict]] = {}
    for row in rows:
        doc = _row_to_uploaded_document(row)
        by_ref.setdefault(doc["entity_ref"], []).append(doc)

    for item in items:
        ref = _clean(item.get(ref_key))
        item["documents"] = by_ref.get(ref, [])
        item["document_count"] = len(item["documents"])
    return items


def list_notification_logs(limit: int = 20) -> list[dict]:
    limit = _normalize_limit(limit)
    rows = _fetch_all(
        f"""
        SELECT * FROM notification_logs
        ORDER BY created_at DESC
        LIMIT {limit}
        """
    )
    return [_row_to_notification_log(row) for row in rows]


def _log_notification(
    *,
    entity_type: str | None,
    entity_ref: str | None,
    event_code: str,
    channel: str,
    recipient: str,
    subject: str | None,
    message_text: str,
    status: str,
    error_text: str | None = None,
) -> None:
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO notification_logs
            (
                entity_type, entity_ref, event_code, channel, recipient, subject,
                message_text, status, error_text
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entity_type,
                entity_ref,
                event_code,
                channel,
                recipient,
                subject,
                message_text,
                status,
                error_text,
            ),
        )
    db.commit()


def _send_email_alert(recipient: str, subject: str, message_text: str) -> tuple[bool, str]:
    recipient = _clean(recipient)
    if not recipient:
        return False, "Missing recipient email."
    if not app.config["SMTP_HOST"] or not app.config["ALERT_FROM_EMAIL"]:
        return False, "SMTP is not configured."

    message = EmailMessage()
    message["From"] = app.config["ALERT_FROM_EMAIL"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(message_text)

    try:
        if app.config["SMTP_USE_SSL"]:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                app.config["SMTP_HOST"], app.config["SMTP_PORT"], context=context, timeout=20
            ) as server:
                if app.config["SMTP_USERNAME"]:
                    server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
                server.send_message(message)
        else:
            with smtplib.SMTP(app.config["SMTP_HOST"], app.config["SMTP_PORT"], timeout=20) as server:
                if app.config["SMTP_USE_TLS"]:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                if app.config["SMTP_USERNAME"]:
                    server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
                server.send_message(message)
        return True, "Email sent."
    except Exception as exc:
        return False, str(exc)


def _send_sms_alert(recipient: str, message_text: str) -> tuple[bool, str]:
    recipient = _normalize_mobile(recipient)
    if not recipient:
        return False, "Missing recipient mobile number."

    try:
        if app.config["SMS_WEBHOOK_URL"]:
            body = json.dumps({"recipient": recipient, "message": message_text}).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if app.config["SMS_WEBHOOK_TOKEN"]:
                headers["Authorization"] = f"Bearer {app.config['SMS_WEBHOOK_TOKEN']}"
            request_obj = urllib.request.Request(
                app.config["SMS_WEBHOOK_URL"], data=body, headers=headers, method="POST"
            )
            with urllib.request.urlopen(request_obj, timeout=20):
                return True, "SMS webhook accepted."

        if app.config["SMS77_API_KEY"]:
            payload = urllib.parse.urlencode(
                {
                    "to": recipient,
                    "text": message_text,
                    "from": "GramSetu",
                }
            ).encode("utf-8")
            request_obj = urllib.request.Request(
                "https://sms77io.p.rapidapi.com/sms",
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "x-rapidapi-host": "sms77io.p.rapidapi.com",
                    "x-rapidapi-key": app.config["SMS77_API_KEY"],
                },
                method="POST",
            )
            with urllib.request.urlopen(request_obj, timeout=20) as response:
                response_text = response.read().decode("utf-8", errors="ignore")
                if response.status == 200 and response_text.strip() and not response_text.startswith("ERROR"):
                    return True, f"SMS sent via SMS77. Response: {response_text}"
                else:
                    return False, f"SMS77 error: {response_text}"

        if (
            app.config["TWILIO_ACCOUNT_SID"]
            and app.config["TWILIO_AUTH_TOKEN"]
            and app.config["TWILIO_FROM_NUMBER"]
        ):
            payload = urllib.parse.urlencode(
                {
                    "To": recipient,
                    "From": app.config["TWILIO_FROM_NUMBER"],
                    "Body": message_text,
                }
            ).encode("utf-8")
            token = base64.b64encode(
                f"{app.config['TWILIO_ACCOUNT_SID']}:{app.config['TWILIO_AUTH_TOKEN']}".encode("utf-8")
            ).decode("utf-8")
            request_obj = urllib.request.Request(
                f"https://api.twilio.com/2010-04-01/Accounts/{app.config['TWILIO_ACCOUNT_SID']}/Messages.json",
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {token}",
                },
                method="POST",
            )
            with urllib.request.urlopen(request_obj, timeout=20):
                return True, "SMS sent."
    except urllib.error.HTTPError as exc:
        return False, exc.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return False, str(exc)

    return False, "No SMS provider is configured."


def _dispatch_alerts(
    *,
    entity_type: str,
    entity_ref: str,
    event_code: str,
    recipient_email: str | None,
    recipient_mobile: str | None,
    subject: str,
    message_text: str,
    admin_subject: str | None = None,
    admin_message_text: str | None = None,
) -> None:
    recipient_email = _clean(recipient_email)
    recipient_mobile = _clean(recipient_mobile)
    admin_email = _clean(app.config["ADMIN_ALERT_EMAIL"])
    admin_mobile = _clean(app.config["ADMIN_ALERT_MOBILE"])

    targets = [
        ("email", recipient_email, subject, message_text),
        ("sms", recipient_mobile, None, message_text),
        ("email", admin_email, admin_subject or subject, admin_message_text or message_text),
        ("sms", admin_mobile, None, admin_message_text or message_text),
    ]

    for channel, recipient, item_subject, item_message in targets:
        if not recipient:
            continue
        if channel == "email":
            ok, detail = _send_email_alert(recipient, item_subject or subject, item_message)
        else:
            ok, detail = _send_sms_alert(recipient, item_message)
        _log_notification(
            entity_type=entity_type,
            entity_ref=entity_ref,
            event_code=event_code,
            channel=channel,
            recipient=recipient,
            subject=item_subject,
            message_text=item_message,
            status="sent" if ok else "failed",
            error_text=None if ok else detail,
        )


def _build_chatbot_context() -> str:
    services = list_service_catalog(published_only=True, limit=10)
    notices = list_notices(published_only=True, limit=5)
    built_in_services = ", ".join(labels["en"] for labels in SERVICE_LABELS.values())
    dynamic_lines = "\n".join(
        f"- {item['title']} ({item['department']}): {item['summary']}" for item in services
    )
    notice_lines = "\n".join(
        f"- {item['title']} on {item['issued_on']}: {item['summary']}" for item in notices
    )
    return (
        "Built-in services: "
        + built_in_services
        + "\nPublished schemes:\n"
        + (dynamic_lines or "- None")
        + "\nLatest notices:\n"
        + (notice_lines or "- None")
    )


def _local_chatbot_reply(question: str) -> str:
    lowered = _clean(question).lower()
    if any(term in lowered for term in ("complaint", "ફરિયાદ")):
        return "Complaint submit karva mate Complaints page kholo, form bharo, ane Complaint ID thi status track karo."
    if any(term in lowered for term in ("certificate", "scheme", "yojana", "service", "સેવા", "યોજના")):
        schemes = list_service_catalog(published_only=True, limit=5)
        if schemes:
            names = ", ".join(item["title"] for item in schemes[:5])
            return f"Available digital schemes/forms ma aa options chhe: {names}. Vadhare details mate Services page kholo."
        return "Services page par built-in certificate ane request forms available chhe. Tya thi online apply kari shako."
    if any(term in lowered for term in ("notice", "circular", "જાહેર", "notice")):
        notices = list_notices(published_only=True, limit=3)
        if notices:
            names = ", ".join(item["title"] for item in notices)
            return f"Latest public notices ma aa include chhe: {names}. Full details Notices page par mali jashe."
        return "Current ma koi public notice publish nathi. Thodi vaar pachhi fari check karo."
    if any(term in lowered for term in ("admin", "login")):
        return "Admin access mate /admin/login kholo ane admin/staff mobile-password vapro."
    return (
        "Hu GramSetu assistant chhu. Tame services, schemes, complaints, notices, ke application tracking vishe puchhi shako."
    )


def _openai_chatbot_reply(question: str) -> tuple[str, str]:
    api_key = _clean(app.config["OPENAI_API_KEY"])
    if not api_key:
        return _local_chatbot_reply(question), "local"

    instructions = (
        "You are the GramSetu village e-governance assistant. Answer briefly, accurately, and only about "
        "GramSetu services, notices, applications, complaints, and admin help. If the answer is not in context, "
        "say what page the citizen should open next. Reply in Gujarati if the user's question appears Gujarati, "
        "otherwise reply in English."
    )
    payload = {
        "model": app.config["OPENAI_CHAT_MODEL"],
        "instructions": instructions,
        "input": f"Portal context:\n{_build_chatbot_context()}\n\nCitizen question:\n{question}",
        "reasoning": {"effort": "low"},
    }

    request_obj = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        answer = _extract_openai_text(body)
        return (answer or _local_chatbot_reply(question)), "openai"
    except Exception:
        return _local_chatbot_reply(question), "local"


def get_service_catalog_by_id(
    scheme_id: str | int | None, *, published_only: bool = False
) -> dict | None:
    if not scheme_id:
        return None
    row = _fetch_one(
        """
        SELECT * FROM service_catalog
        WHERE id = %s
        """
        + (" AND is_published = 1" if published_only else ""),
        (scheme_id,),
    )
    return _row_to_service_catalog(row)


def get_service_catalog_by_code(code: str, *, published_only: bool = False) -> dict | None:
    cleaned_code = _normalize_field_name(code)
    if not cleaned_code:
        return None
    row = _fetch_one(
        """
        SELECT * FROM service_catalog
        WHERE code = %s
        """
        + (" AND is_published = 1" if published_only else ""),
        (cleaned_code,),
    )
    return _row_to_service_catalog(row)


def get_service_catalog_by_slug(slug: str, *, published_only: bool = True) -> dict | None:
    cleaned_slug = _slugify(slug)
    if not cleaned_slug:
        return None
    row = _fetch_one(
        """
        SELECT * FROM service_catalog
        WHERE slug = %s
        """
        + (" AND is_published = 1" if published_only else ""),
        (cleaned_slug,),
    )
    return _row_to_service_catalog(row)


def list_service_catalog(published_only: bool = False, limit: int = 50) -> list[dict]:
    limit = _normalize_limit(limit)
    query = """
        SELECT * FROM service_catalog
    """
    if published_only:
        query += " WHERE is_published = 1"
    query += f" ORDER BY is_published DESC, updated_at DESC LIMIT {limit}"
    rows = _fetch_all(query)
    services = [_row_to_service_catalog(row) for row in rows]
    for service in services:
        service["field_count"] = len(service["fields"])
    return services


def create_service_catalog(form_data: dict, *, created_by_user_id: int | None = None) -> dict:
    title = _clean(form_data.get("title"))
    code = _normalize_field_name(form_data.get("code") or title)
    slug = _slugify(form_data.get("slug") or code or title)
    department = _clean(form_data.get("department")) or "Gram Panchayat"
    category = _clean(form_data.get("category")) or "Government Scheme"
    summary = _clean(form_data.get("summary"))
    intro = _clean(form_data.get("intro")) or None
    eligibility = _clean(form_data.get("eligibility")) or None
    documents = _clean(form_data.get("documents")) or None
    instructions = _clean(form_data.get("instructions")) or None
    fields = _parse_form_fields_config(form_data.get("fields_json"))
    is_published = _coerce_checkbox(form_data.get("is_published"))

    if not title:
        raise ValueError("Scheme title is required.")
    if not code:
        raise ValueError("Scheme code is required.")
    if not slug:
        raise ValueError("Scheme slug is required.")
    if code in SERVICE_LABELS:
        raise ValueError("This scheme code is reserved for a built-in service.")
    if slug in RESERVED_SERVICE_SLUGS:
        raise ValueError("This public slug is reserved for an existing service route.")
    if not summary:
        raise ValueError("Scheme summary is required.")

    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO service_catalog
                (
                    code, slug, title, department, category, summary, intro,
                    eligibility, documents, instructions, fields_json, is_published,
                    created_by_user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    slug,
                    title,
                    department,
                    category,
                    summary,
                    intro,
                    eligibility,
                    documents,
                    instructions,
                    json.dumps(fields),
                    int(is_published),
                    created_by_user_id,
                ),
            )
            scheme_id = cursor.lastrowid
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Scheme code or slug already exists.") from exc

    return get_service_catalog_by_id(scheme_id)


def update_service_catalog(scheme_id: str | int | None, form_data: dict) -> dict:
    existing = get_service_catalog_by_id(scheme_id)
    if existing is None:
        raise ValueError("Scheme was not found.")

    title = _clean(form_data.get("title"))
    department = _clean(form_data.get("department")) or "Gram Panchayat"
    category = _clean(form_data.get("category")) or "Government Scheme"
    summary = _clean(form_data.get("summary"))
    intro = _clean(form_data.get("intro")) or None
    eligibility = _clean(form_data.get("eligibility")) or None
    documents = _clean(form_data.get("documents")) or None
    instructions = _clean(form_data.get("instructions")) or None
    fields = _parse_form_fields_config(form_data.get("fields_json"))
    is_published = _coerce_checkbox(form_data.get("is_published"))

    if not title:
        raise ValueError("Scheme title is required.")
    if not summary:
        raise ValueError("Scheme summary is required.")

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE service_catalog
            SET title = %s,
                department = %s,
                category = %s,
                summary = %s,
                intro = %s,
                eligibility = %s,
                documents = %s,
                instructions = %s,
                fields_json = %s,
                is_published = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                title,
                department,
                category,
                summary,
                intro,
                eligibility,
                documents,
                instructions,
                json.dumps(fields),
                int(is_published),
                existing["id"],
            ),
        )
    db.commit()
    return get_service_catalog_by_id(existing["id"])


def delete_service_catalog(scheme_id: str | int | None) -> bool:
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM service_catalog WHERE id = %s", (scheme_id,))
        changed = cursor.rowcount
    db.commit()
    return changed > 0


def list_notices(*, published_only: bool = True, limit: int = 50) -> list[dict]:
    limit = _normalize_limit(limit)
    query = """
        SELECT * FROM notices
    """
    if published_only:
        query += " WHERE is_published = 1"
    query += f" ORDER BY issued_on DESC, created_at DESC LIMIT {limit}"
    rows = _fetch_all(query)
    return [_row_to_notice(row) for row in rows]


def get_notice_by_id(notice_id: str | int | None) -> dict | None:
    if not notice_id:
        return None
    row = _fetch_one("SELECT * FROM notices WHERE id = %s", (notice_id,))
    return _row_to_notice(row)


def create_notice(form_data: dict, *, created_by_user_id: int | None = None) -> dict:
    title = _clean(form_data.get("title"))
    reference_no = _clean(form_data.get("reference_no")) or None
    summary = _clean(form_data.get("summary"))
    body = _clean(form_data.get("body")) or None
    issued_on = _parse_date_input(form_data.get("issued_on"), field_label="Issued date", required=True)
    download_url = _clean(form_data.get("download_url")) or None
    is_published = _coerce_checkbox(form_data.get("is_published"))

    if not title:
        raise ValueError("Notice title is required.")
    if not summary:
        raise ValueError("Notice summary is required.")

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO notices
            (
                title, reference_no, summary, body, issued_on, download_url,
                is_published, created_by_user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                title,
                reference_no,
                summary,
                body,
                issued_on,
                download_url,
                int(is_published),
                created_by_user_id,
            ),
        )
        notice_id = cursor.lastrowid
    db.commit()
    return get_notice_by_id(notice_id)


def update_notice(notice_id: str | int | None, form_data: dict) -> dict:
    existing = get_notice_by_id(notice_id)
    if existing is None:
        raise ValueError("Notice was not found.")

    title = _clean(form_data.get("title"))
    reference_no = _clean(form_data.get("reference_no")) or None
    summary = _clean(form_data.get("summary"))
    body = _clean(form_data.get("body")) or None
    issued_on = _parse_date_input(form_data.get("issued_on"), field_label="Issued date", required=True)
    download_url = _clean(form_data.get("download_url")) or None
    is_published = _coerce_checkbox(form_data.get("is_published"))

    if not title:
        raise ValueError("Notice title is required.")
    if not summary:
        raise ValueError("Notice summary is required.")

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE notices
            SET title = %s,
                reference_no = %s,
                summary = %s,
                body = %s,
                issued_on = %s,
                download_url = %s,
                is_published = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                title,
                reference_no,
                summary,
                body,
                issued_on,
                download_url,
                int(is_published),
                existing["id"],
            ),
        )
    db.commit()
    return get_notice_by_id(existing["id"])


def delete_notice(notice_id: str | int | None) -> bool:
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM notices WHERE id = %s", (notice_id,))
        changed = cursor.rowcount
    db.commit()
    return changed > 0


def create_service_request(service_code: str, form_data: dict, files=None) -> dict:
    applicant_name = _clean(
        form_data.get("applicant_name")
        or form_data.get("head_name")
        or form_data.get("full_name")
    )
    mobile = _clean(form_data.get("mobile"))

    if not applicant_name:
        raise ValueError(_translate("Applicant name is required."))
    if not mobile:
        raise ValueError(_translate("Mobile number is required."))

    payload = {key: _clean(value) for key, value in form_data.items() if _clean(value)}
    email = _clean(form_data.get("email")) or None
    uploaded_items = _normalize_uploaded_items(files)
    if uploaded_items:
        payload["uploaded_file_fields"] = sorted(
            {item["field_name"] for item in uploaded_items}
        )

    db = get_db()
    for _ in range(6):
        request_id = _generate_token("SRV")
        try:
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO service_requests
                    (request_id, service_code, applicant_name, mobile, email, details_json, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'submitted')
                    """,
                    (
                        request_id,
                        service_code,
                        applicant_name,
                        mobile,
                        email,
                        json.dumps(payload),
                    ),
                )
            _save_uploaded_documents(
                "service_request",
                request_id,
                uploaded_items,
                uploaded_by_mobile=mobile,
            )
            db.commit()

            created_request = get_service_request_by_request_id(request_id) or find_service_request(
                request_id, mobile
            )
            _dispatch_alerts(
                entity_type="service_request",
                entity_ref=request_id,
                event_code="service_submitted",
                recipient_email=email,
                recipient_mobile=mobile,
                subject=f"Application Submitted: {created_request['service_name']}",
                message_text=(
                    f"Your application {request_id} for {created_request['service_name']} was submitted successfully. "
                    f"Current status: {created_request['status']}."
                ),
                admin_subject=f"New Application Received: {created_request['service_name']}",
                admin_message_text=(
                    f"New service application {request_id} received for {created_request['service_name']} "
                    f"from {applicant_name} ({mobile})."
                ),
            )
            return created_request
        except IntegrityError as exc:
            db.rollback()
            if exc.args and exc.args[0] == 1062:
                continue
            raise RuntimeError(_translate("Could not save service request.")) from exc

    raise RuntimeError(_translate("Could not generate a unique request ID. Please retry."))


def create_complaint(form_data: dict, files=None) -> dict:
    full_name = _clean(form_data.get("full_name"))
    mobile = _clean(form_data.get("mobile"))
    category = _clean(form_data.get("category"))
    location = _clean(form_data.get("location"))
    details = _clean(form_data.get("details"))
    email = _clean(form_data.get("email")) or None
    uploaded_items = _normalize_uploaded_items(files)

    if not full_name:
        raise ValueError(_translate("Full name is required."))
    if not mobile:
        raise ValueError(_translate("Mobile number is required."))
    if not category:
        raise ValueError(_translate("Complaint category is required."))
    if not location:
        raise ValueError(_translate("Location is required."))
    if not details:
        raise ValueError(_translate("Complaint details are required."))

    db = get_db()
    for _ in range(6):
        complaint_id = _generate_token("CMP")
        try:
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO complaints
                    (complaint_id, full_name, mobile, email, category, location, details, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
                    """,
                    (complaint_id, full_name, mobile, email, category, location, details),
                )
            _save_uploaded_documents(
                "complaint",
                complaint_id,
                uploaded_items,
                uploaded_by_mobile=mobile,
            )
            db.commit()

            created_complaint = get_complaint_by_id(complaint_id) or find_complaint(
                complaint_id, mobile
            )
            _dispatch_alerts(
                entity_type="complaint",
                entity_ref=complaint_id,
                event_code="complaint_submitted",
                recipient_email=email,
                recipient_mobile=mobile,
                subject=f"Complaint Registered: {complaint_id}",
                message_text=(
                    f"Your complaint {complaint_id} has been registered under category {category}. "
                    f"Current status: {created_complaint['status']}."
                ),
                admin_subject=f"New Complaint Registered: {complaint_id}",
                admin_message_text=(
                    f"New complaint {complaint_id} received from {full_name} ({mobile}) "
                    f"for category {category} at {location}."
                ),
            )
            return created_complaint
        except IntegrityError as exc:
            db.rollback()
            if exc.args and exc.args[0] == 1062:
                continue
            raise RuntimeError(_translate("Could not save complaint.")) from exc

    raise RuntimeError(_translate("Could not generate a unique complaint ID. Please retry."))


def find_service_request(request_id: str, mobile: str) -> dict | None:
    row = _fetch_one(
        """
        SELECT * FROM service_requests
        WHERE request_id = %s AND mobile = %s
        """,
        (_clean(request_id), _clean(mobile)),
    )
    item = _row_to_service_request(row)
    if item:
        item["documents"] = list_uploaded_documents("service_request", item["request_id"])
        item["document_count"] = len(item["documents"])
    return item


def find_complaint(complaint_id: str, mobile: str) -> dict | None:
    row = _fetch_one(
        """
        SELECT * FROM complaints
        WHERE complaint_id = %s AND mobile = %s
        """,
        (_clean(complaint_id), _clean(mobile)),
    )
    item = _row_to_complaint(row)
    if item:
        item["documents"] = list_uploaded_documents("complaint", item["complaint_id"])
        item["document_count"] = len(item["documents"])
    return item


def list_service_requests(status: str | None = None, limit: int = 50) -> list[dict]:
    limit = _normalize_limit(limit)
    if status and status in SERVICE_STATUS_OPTIONS:
        rows = _fetch_all(
            f"""
            SELECT * FROM service_requests
            WHERE status = %s
            ORDER BY submitted_at DESC
            LIMIT {limit}
            """,
            (status,),
        )
    else:
        rows = _fetch_all(
            f"""
            SELECT * FROM service_requests
            ORDER BY submitted_at DESC
            LIMIT {limit}
            """
        )
    items = [_row_to_service_request(row) for row in rows]
    return _attach_documents_to_records(items, entity_type="service_request", ref_key="request_id")


def list_complaints(status: str | None = None, limit: int = 50) -> list[dict]:
    limit = _normalize_limit(limit)
    if status and status in COMPLAINT_STATUS_OPTIONS:
        rows = _fetch_all(
            f"""
            SELECT * FROM complaints
            WHERE status = %s
            ORDER BY created_at DESC
            LIMIT {limit}
            """,
            (status,),
        )
    else:
        rows = _fetch_all(
            f"""
            SELECT * FROM complaints
            ORDER BY created_at DESC
            LIMIT {limit}
            """
        )
    items = [_row_to_complaint(row) for row in rows]
    return _attach_documents_to_records(items, entity_type="complaint", ref_key="complaint_id")


def update_service_status(request_id: str, status: str) -> bool:
    if status not in SERVICE_STATUS_OPTIONS:
        return False

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE service_requests
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE request_id = %s
            """,
            (status, request_id),
        )
        changed = cursor.rowcount
    db.commit()
    if changed > 0:
        service_request = get_service_request_by_request_id(request_id)
        if service_request:
            _dispatch_alerts(
                entity_type="service_request",
                entity_ref=request_id,
                event_code="service_status_updated",
                recipient_email=service_request["email"],
                recipient_mobile=service_request["mobile"],
                subject=f"Application Status Updated: {request_id}",
                message_text=(
                    f"Your application {request_id} for {service_request['service_name']} is now "
                    f"marked as {status.replace('_', ' ')}."
                ),
                admin_subject=f"Application Updated: {request_id}",
                admin_message_text=(
                    f"Application {request_id} for {service_request['service_name']} was updated "
                    f"to {status.replace('_', ' ')}."
                ),
            )
    return changed > 0


def update_complaint_status(complaint_id: str, status: str, department: str) -> bool:
    if status not in COMPLAINT_STATUS_OPTIONS:
        return False

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE complaints
            SET status = %s, assigned_department = %s, updated_at = CURRENT_TIMESTAMP
            WHERE complaint_id = %s
            """,
            (status, _clean(department) or "General", complaint_id),
        )
        changed = cursor.rowcount
    db.commit()
    if changed > 0:
        complaint = get_complaint_by_id(complaint_id)
        if complaint:
            _dispatch_alerts(
                entity_type="complaint",
                entity_ref=complaint_id,
                event_code="complaint_status_updated",
                recipient_email=complaint["email"],
                recipient_mobile=complaint["mobile"],
                subject=f"Complaint Status Updated: {complaint_id}",
                message_text=(
                    f"Your complaint {complaint_id} is now {status.replace('_', ' ')} and assigned to "
                    f"{complaint['assigned_department']}."
                ),
                admin_subject=f"Complaint Updated: {complaint_id}",
                admin_message_text=(
                    f"Complaint {complaint_id} was updated to {status.replace('_', ' ')} under "
                    f"{complaint['assigned_department']}."
                ),
            )
    return changed > 0


def _count(query: str, params: tuple = ()) -> int:
    row = _fetch_one(query, params)
    return int(row["total"]) if row else 0


def get_dashboard_metrics() -> dict:
    total_requests = _count("SELECT COUNT(*) AS total FROM service_requests")
    pending_requests = _count(
        """
        SELECT COUNT(*) AS total FROM service_requests
        WHERE status IN ('submitted', 'under_review')
        """
    )
    approved_requests = _count(
        "SELECT COUNT(*) AS total FROM service_requests WHERE status = 'approved'"
    )

    total_complaints = _count("SELECT COUNT(*) AS total FROM complaints")
    open_complaints = _count(
        """
        SELECT COUNT(*) AS total FROM complaints
        WHERE status IN ('open', 'in_progress')
        """
    )
    resolved_complaints = _count(
        "SELECT COUNT(*) AS total FROM complaints WHERE status IN ('resolved', 'closed')"
    )
    total_schemes = _count("SELECT COUNT(*) AS total FROM service_catalog")
    published_schemes = _count(
        "SELECT COUNT(*) AS total FROM service_catalog WHERE is_published = 1"
    )
    total_notices = _count("SELECT COUNT(*) AS total FROM notices")
    published_notices = _count(
        "SELECT COUNT(*) AS total FROM notices WHERE is_published = 1"
    )
    total_users = _count("SELECT COUNT(*) AS total FROM users")
    total_documents = _count("SELECT COUNT(*) AS total FROM uploaded_documents")
    total_alerts = _count("SELECT COUNT(*) AS total FROM notification_logs")
    successful_alerts = _count(
        "SELECT COUNT(*) AS total FROM notification_logs WHERE status = 'sent'"
    )

    total_work = total_requests + total_complaints
    completed_work = approved_requests + resolved_complaints
    digital_efficiency = (
        round((completed_work * 100) / total_work, 1) if total_work else 0.0
    )

    return {
        "total_requests": total_requests,
        "pending_requests": pending_requests,
        "approved_requests": approved_requests,
        "total_complaints": total_complaints,
        "open_complaints": open_complaints,
        "resolved_complaints": resolved_complaints,
        "total_schemes": total_schemes,
        "published_schemes": published_schemes,
        "total_notices": total_notices,
        "published_notices": published_notices,
        "total_users": total_users,
        "total_documents": total_documents,
        "total_alerts": total_alerts,
        "successful_alerts": successful_alerts,
        "digital_efficiency": digital_efficiency,
    }


def handle_service_application(service_code: str, template_name: str):
    submission = None
    submission_error = None

    if request.method == "POST":
        try:
            submission = create_service_request(
                service_code,
                request.form.to_dict(),
                request.files,
            )
        except (RuntimeError, ValueError) as exc:
            submission_error = str(exc)

    return render_template(
        template_name,
        service_name=_service_name(service_code),
        submission=submission,
        submission_error=submission_error,
    )


def handle_dynamic_service_application(scheme: dict):
    submission = None
    submission_error = None

    if request.method == "POST":
        try:
            _validate_dynamic_service_submission(scheme["fields"], request.form, request.files)
            submission = create_service_request(
                scheme["code"],
                request.form.to_dict(),
                request.files,
            )
        except (RuntimeError, ValueError) as exc:
            submission_error = str(exc)

    return render_template(
        "services/dynamic_service.html",
        scheme=scheme,
        service_name=scheme["title"],
        submission=submission,
        submission_error=submission_error,
    )


# Public pages
@app.get("/manifest.webmanifest")
def web_manifest():
    return app.send_static_file("manifest.webmanifest")


@app.get("/sw.js")
def service_worker():
    return send_file(
        os.path.join(app.static_folder, "sw.js"),
        mimetype="application/javascript",
        max_age=0,
    )


@app.get("/set-language/<lang_code>")
def set_language(lang_code: str):
    selected = _clean(lang_code).lower()
    if selected in SUPPORTED_LANGUAGES:
        session["lang"] = selected

    next_url = request.args.get("next")
    if not _is_safe_next(next_url):
        next_url = url_for("home")
    return redirect(next_url)


@app.get("/")
def home():
    return render_template("index.html", digital_metrics=get_dashboard_metrics())


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/services")
def services_index():
    return render_template(
        "services/index.html",
        dynamic_schemes=list_service_catalog(published_only=True, limit=50),
        latest_requests=list_service_requests(limit=5),
    )


@app.get("/services/track")
def track_service_request():
    request_id = _clean(request.args.get("request_id"))
    mobile = _clean(request.args.get("mobile"))

    tracked_application = None
    tracking_error = None

    if request_id or mobile:
        if not request_id or not mobile:
            tracking_error = _translate(
                "Enter both Request ID and mobile number to track your application."
            )
        else:
            tracked_application = find_service_request(request_id, mobile)
            if tracked_application is None:
                tracking_error = _translate(
                    "No application found. Check your Request ID and mobile number."
                )

    return render_template(
        "services/index.html",
        dynamic_schemes=list_service_catalog(published_only=True, limit=50),
        latest_requests=list_service_requests(limit=5),
        tracked_application=tracked_application,
        tracking_error=tracking_error,
        requested_request_id=request_id,
        requested_mobile=mobile,
    )


@app.route("/services/birth-certificate", methods=["GET", "POST"])
def service_birth_certificate():
    return handle_service_application(
        "birth_certificate", "services/birth_certificate.html"
    )


@app.route("/services/income-certificate", methods=["GET", "POST"])
def service_income_certificate():
    return handle_service_application(
        "income_certificate", "services/income_certificate.html"
    )


@app.route("/services/caste-certificate", methods=["GET", "POST"])
def service_caste_certificate():
    return handle_service_application(
        "caste_certificate", "services/caste_certificate.html"
    )


@app.route("/services/ration-card-update", methods=["GET", "POST"])
def service_ration_card_update():
    return handle_service_application(
        "ration_card_update", "services/ration_card_update.html"
    )


@app.route("/services/water-connection", methods=["GET", "POST"])
def service_water_connection():
    return handle_service_application(
        "water_connection", "services/water_connection.html"
    )


@app.route("/services/<scheme_slug>", methods=["GET", "POST"])
def dynamic_service_application(scheme_slug: str):
    scheme = get_service_catalog_by_slug(scheme_slug, published_only=True)
    if scheme is None:
        abort(404)
    return handle_dynamic_service_application(scheme)


@app.route("/complaints", methods=["GET", "POST"])
def complaints():
    complaint_submission = None
    complaint_error = None
    tracked_complaint = None
    tracking_error = None

    complaint_id = _clean(request.args.get("complaint_id"))
    mobile = _clean(request.args.get("mobile"))

    if request.method == "POST":
        try:
            complaint_submission = create_complaint(request.form.to_dict(), request.files)
        except (RuntimeError, ValueError) as exc:
            complaint_error = str(exc)
    elif complaint_id or mobile:
        if not complaint_id or not mobile:
            tracking_error = _translate(
                "Enter both Complaint ID and mobile number to track your complaint."
            )
        else:
            tracked_complaint = find_complaint(complaint_id, mobile)
            if tracked_complaint is None:
                tracking_error = _translate(
                    "No complaint found. Check your Complaint ID and mobile number."
                )

    return render_template(
        "complaints.html",
        complaint_submission=complaint_submission,
        complaint_error=complaint_error,
        tracked_complaint=tracked_complaint,
        tracking_error=tracking_error,
        requested_complaint_id=complaint_id,
        requested_mobile=mobile,
    )


@app.get("/notices")
def notices():
    return render_template("notices.html", notices=list_notices(published_only=True, limit=100))


@app.get("/contact")
def contact():
    return render_template("contact.html")


@app.post("/api/chatbot")
def chatbot_api():
    payload = request.get_json(silent=True) or {}
    question = _clean(payload.get("message"))
    if not question:
        return jsonify({"error": "Message is required."}), 400

    reply, provider = _openai_chatbot_reply(question)
    return jsonify({"reply": reply, "provider": provider})


@app.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("home"))

    register_error = None
    register_success = None

    if request.method == "POST":
        full_name = _clean(request.form.get("full_name"))
        mobile = _clean(request.form.get("mobile"))
        email = _clean(request.form.get("email")) or None
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name:
            register_error = _translate("Full name is required.")
        elif not mobile:
            register_error = _translate("Mobile number is required.")
        elif not password:
            register_error = _translate("Password is required.")
        elif len(password) < 6:
            register_error = _translate("Password must be at least 6 characters.")
        elif password != confirm_password:
            register_error = _translate("Password and confirm password do not match.")
        else:
            try:
                _insert_user(
                    full_name=full_name,
                    mobile=mobile,
                    email=email,
                    password=password,
                    role="citizen",
                )
                register_success = _translate("Registration successful. Please login.")
            except IntegrityError:
                get_db().rollback()
                register_error = _translate(
                    "Mobile number or email already registered. Try logging in."
                )
            except ValueError as exc:
                register_error = str(exc)

    return render_template(
        "register.html",
        register_error=register_error,
        register_success=register_success,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("home"))

    login_error = None
    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        mobile = _clean(request.form.get("mobile"))
        password = request.form.get("password", "")

        if not mobile or not password:
            login_error = _translate("Enter mobile number and password.")
        else:
            user = _get_user_by_mobile(mobile)
            if (
                user is None
                or user["status"] != "active"
                or not check_password_hash(user["password_hash"], password)
            ):
                login_error = _translate("Invalid login credentials.")
            else:
                _login_user(user)
                target = next_url if _is_safe_next(next_url) else url_for("home")
                return redirect(target)

    return render_template("login.html", login_error=login_error, next_url=next_url)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    current_user = get_current_user()
    login_error = None
    auth_notice = None
    next_url = request.args.get("next") or request.form.get("next") or url_for("admin_dashboard")

    if current_user and current_user["role"] in ADMIN_ROLE_OPTIONS:
        target = next_url if _is_safe_next(next_url) else url_for("admin_dashboard")
        return redirect(target)

    if current_user:
        auth_notice = _translate(
            "You are signed in as {full_name}. Logging in here will switch to an admin or staff account.",
            full_name=current_user["full_name"],
        )

    if request.method == "POST":
        mobile = _clean(request.form.get("mobile"))
        password = request.form.get("password", "")

        if not mobile or not password:
            login_error = _translate("Enter mobile number and password.")
        else:
            user = _get_user_by_mobile(mobile)
            valid_password = bool(
                user and user["status"] == "active" and check_password_hash(user["password_hash"], password)
            )
            if not valid_password:
                login_error = _translate("Invalid login credentials.")
            elif user["role"] not in ADMIN_ROLE_OPTIONS:
                login_error = _translate("Only admin or staff accounts can access the admin panel.")
            else:
                _login_user(user)
                target = next_url if _is_safe_next(next_url) else url_for("admin_dashboard")
                return redirect(target)

    return render_template(
        "admin_login.html",
        auth_notice=auth_notice,
        login_error=login_error,
        next_url=next_url,
    )


@app.get("/logout")
def logout():
    _logout_user()
    return redirect(url_for("home"))


@app.get("/dashboard")
def dashboard():
    return render_template(
        "dashboard.html",
        metrics=get_dashboard_metrics(),
        recent_requests=list_service_requests(limit=8),
        recent_complaints=list_complaints(limit=8),
    )


# Admin pages
@app.get("/admin")
@role_required("admin", "staff")
def admin_dashboard():
    return render_template(
        "admin/admin_dashboard.html",
        metrics=get_dashboard_metrics(),
        latest_applications=list_service_requests(limit=6),
        latest_complaints=list_complaints(limit=6),
        latest_notices=list_notices(published_only=False, limit=5),
        latest_schemes=list_service_catalog(published_only=False, limit=5),
        latest_alerts=list_notification_logs(limit=8),
    )


@app.route("/admin/applications", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_applications():
    admin_message = None

    if request.method == "POST":
        request_id = _clean(request.form.get("request_id"))
        status = _clean(request.form.get("status"))
        if not request_id or status not in SERVICE_STATUS_OPTIONS:
            admin_message = "Invalid application update request."
        elif update_service_status(request_id, status):
            admin_message = f"Application {request_id} updated to {status}."
        else:
            admin_message = f"Application {request_id} was not found."

    status_filter = _clean(request.args.get("status"))
    if status_filter not in SERVICE_STATUS_OPTIONS:
        status_filter = ""

    return render_template(
        "admin/applications.html",
        applications=list_service_requests(status=status_filter or None, limit=100),
        status_options=SERVICE_STATUS_OPTIONS,
        active_filter=status_filter,
        admin_message=admin_message,
    )


@app.route("/admin/complaints", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_complaints():
    admin_message = None

    if request.method == "POST":
        complaint_id = _clean(request.form.get("complaint_id"))
        status = _clean(request.form.get("status"))
        department = _clean(request.form.get("department"))

        if not complaint_id or status not in COMPLAINT_STATUS_OPTIONS:
            admin_message = "Invalid complaint update request."
        elif update_complaint_status(complaint_id, status, department):
            admin_message = f"Complaint {complaint_id} updated to {status}."
        else:
            admin_message = f"Complaint {complaint_id} was not found."

    status_filter = _clean(request.args.get("status"))
    if status_filter not in COMPLAINT_STATUS_OPTIONS:
        status_filter = ""

    return render_template(
        "admin/complaints.html",
        complaints=list_complaints(status=status_filter or None, limit=100),
        status_options=COMPLAINT_STATUS_OPTIONS,
        active_filter=status_filter,
        admin_message=admin_message,
    )


@app.route("/admin/schemes", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_schemes():
    admin_message = None
    admin_error = None
    current_user = get_current_user()
    edit_id = _clean(request.args.get("edit"))

    if request.method == "POST":
        action = _clean(request.form.get("action")) or "create"
        try:
            if action == "create":
                created = create_service_catalog(
                    request.form.to_dict(),
                    created_by_user_id=current_user["id"] if current_user else None,
                )
                admin_message = f"Scheme '{created['title']}' created successfully."
            elif action == "update":
                updated = update_service_catalog(
                    request.form.get("scheme_id"), request.form.to_dict()
                )
                admin_message = f"Scheme '{updated['title']}' updated successfully."
                edit_id = str(updated["id"])
            elif action == "delete":
                scheme_id = request.form.get("scheme_id")
                if delete_service_catalog(scheme_id):
                    admin_message = "Scheme removed successfully."
                    edit_id = ""
                else:
                    admin_error = "Scheme was not found."
            else:
                admin_error = "Invalid scheme management request."
        except (RuntimeError, ValueError) as exc:
            admin_error = str(exc)
            edit_id = _clean(request.form.get("scheme_id")) or edit_id

    editing_scheme = get_service_catalog_by_id(edit_id) if edit_id else None
    return render_template(
        "admin/schemes.html",
        schemes=list_service_catalog(published_only=False, limit=200),
        editing_scheme=editing_scheme,
        field_config_example=DEFAULT_SCHEME_FIELD_TEMPLATE,
        admin_message=admin_message,
        admin_error=admin_error,
    )


@app.route("/admin/notices", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_notices():
    admin_message = None
    admin_error = None
    current_user = get_current_user()
    edit_id = _clean(request.args.get("edit"))

    if request.method == "POST":
        action = _clean(request.form.get("action")) or "create"
        try:
            if action == "create":
                created = create_notice(
                    request.form.to_dict(),
                    created_by_user_id=current_user["id"] if current_user else None,
                )
                admin_message = f"Notice '{created['title']}' created successfully."
            elif action == "update":
                updated = update_notice(request.form.get("notice_id"), request.form.to_dict())
                admin_message = f"Notice '{updated['title']}' updated successfully."
                edit_id = str(updated["id"])
            elif action == "delete":
                if delete_notice(request.form.get("notice_id")):
                    admin_message = "Notice removed successfully."
                    edit_id = ""
                else:
                    admin_error = "Notice was not found."
            else:
                admin_error = "Invalid notice management request."
        except (RuntimeError, ValueError) as exc:
            admin_error = str(exc)
            edit_id = _clean(request.form.get("notice_id")) or edit_id

    editing_notice = get_notice_by_id(edit_id) if edit_id else None
    return render_template(
        "admin/notices.html",
        notices=list_notices(published_only=False, limit=100),
        editing_notice=editing_notice,
        admin_message=admin_message,
        admin_error=admin_error,
    )


@app.route("/admin/users", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_users():
    admin_message = None
    admin_error = None
    current_user = get_current_user()

    if request.method == "POST":
        action = _clean(request.form.get("action"))
        try:
            if action == "create":
                created = create_admin_managed_user(request.form.to_dict())
                admin_message = f"User '{created['full_name']}' created successfully."
            elif action == "update":
                changed = update_user_admin_access(
                    request.form.get("user_id"),
                    role=_clean(request.form.get("role")),
                    status=_clean(request.form.get("status")),
                    current_user_id=current_user["id"] if current_user else None,
                )
                admin_message = (
                    "User access updated successfully."
                    if changed
                    else "No user changes were applied."
                )
            else:
                admin_error = "Invalid user management request."
        except (RuntimeError, ValueError) as exc:
            admin_error = str(exc)

    return render_template(
        "admin/users.html",
        users=list_users(limit=250),
        role_options=USER_ROLE_OPTIONS,
        status_options=USER_STATUS_OPTIONS,
        admin_message=admin_message,
        admin_error=admin_error,
    )


@app.get("/admin/documents/<int:document_id>")
@role_required("admin", "staff")
def admin_download_document(document_id: int):
    document = get_uploaded_document_by_id(document_id)
    if document is None:
        abort(404)

    absolute_path = os.path.normpath(os.path.join(_upload_root(), document["stored_path"]))
    upload_root = os.path.normpath(_upload_root())
    if not absolute_path.startswith(upload_root) or not os.path.exists(absolute_path):
        abort(404)

    return send_file(
        absolute_path,
        as_attachment=True,
        download_name=document["original_name"],
        mimetype=document["mime_type"] or "application/octet-stream",
    )


@app.get("/api/digital-system")
def digital_system_api():
    service_types = {code: labels["en"] for code, labels in SERVICE_LABELS.items()}
    service_types.update(
        {item["code"]: item["title"] for item in list_service_catalog(published_only=True, limit=250)}
    )
    return jsonify(
        {
            "system": "GramSetu Digital Seva Engine",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "metrics": get_dashboard_metrics(),
            "service_types": service_types,
            "service_status_options": list(SERVICE_STATUS_OPTIONS),
            "complaint_status_options": list(COMPLAINT_STATUS_OPTIONS),
        }
    )


with app.app_context():
    try:
        init_db()
    except MySQLError as exc:
        raise RuntimeError(
            "MySQL initialization failed. Verify MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DB."
        ) from exc


if __name__ == "__main__":
    debug_mode = _clean(os.getenv("FLASK_DEBUG", "0")).lower() in {"1", "true", "yes", "on"}
    host = _clean(os.getenv("FLASK_RUN_HOST")) or "0.0.0.0"
    port = int(_clean(os.getenv("PORT")) or _clean(os.getenv("FLASK_RUN_PORT")) or "5000")
    app.run(host=host, port=port, debug=debug_mode)
