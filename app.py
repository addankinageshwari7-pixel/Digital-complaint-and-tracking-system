import os, io, random, base64
from datetime import datetime, timedelta
from flask import (Flask, render_template, request, redirect, url_for, flash,
                   jsonify, send_file, abort)
from flask_login import (LoginManager, login_user, logout_user, login_required,
                         current_user)
from werkzeug.utils import secure_filename
import pandas as pd
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image as RLImage)

from models import db
from models.user import User
from models.complaint import Complaint, AdminNote

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, 'database')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(DB_DIR, 'complaints.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

CATEGORIES = ['Infrastructure', 'Water', 'Electricity', 'Internet', 'Safety',
              'Education', 'Healthcare', 'Transport', 'Customer Service', 'Other']
STATUSES = ['Submitted', 'Under Review', 'Assigned', 'In Progress', 'Resolved', 'Closed']
PRIORITIES = ['Low', 'Medium', 'High', 'Critical']
DEPARTMENTS = ['Public Works', 'Water Board', 'Electricity Board', 'IT Cell',
               'Police', 'Education Dept', 'Health Dept', 'Transport Dept',
               'Customer Care', 'General Admin']

ALLOWED_EXT = {'png','jpg','jpeg','pdf','doc','docx','txt'}

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

def gen_complaint_id():
    year = datetime.utcnow().year
    for _ in range(10):
        cid = f"CMP-{year}-{random.randint(100000, 999999)}"
        if not Complaint.query.filter_by(complaint_id=cid).first():
            return cid
    return f"CMP-{year}-{random.randint(1000000, 9999999)}"

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED_EXT

# ---------- Routes ----------
@app.route('/')
def index():
    total = Complaint.query.count()
    resolved = Complaint.query.filter(Complaint.status.in_(['Resolved','Closed'])).count()
    active = Complaint.query.filter(~Complaint.status.in_(['Resolved','Closed'])).count()
    users = db.session.query(Complaint.email).distinct().count()
    rate = round((resolved/total*100), 1) if total else 0
    stats = {'total': total, 'resolved': resolved, 'active': active,
             'users': users, 'rate': rate}
    return render_template('index.html', stats=stats)

@app.route('/register-complaint', methods=['GET','POST'])
def register_complaint():
    if request.method == 'POST':
        f = request.form
        doc_name = None
        file = request.files.get('document')
        if file and file.filename and allowed_file(file.filename):
            doc_name = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
            file.save(os.path.join(UPLOAD_DIR, doc_name))
        c = Complaint(
            complaint_id=gen_complaint_id(),
            name=f.get('name','').strip(),
            email=f.get('email','').strip().lower(),
            phone=f.get('phone','').strip(),
            title=f.get('title','').strip(),
            category=f.get('category','Other'),
            description=f.get('description','').strip(),
            location=f.get('location','').strip(),
            priority=f.get('priority','Medium'),
            document=doc_name,
        )
        db.session.add(c); db.session.commit()
        flash(f'Complaint registered successfully! Your ID: {c.complaint_id}', 'success')
        return redirect(url_for('track_complaint', cid=c.complaint_id, email=c.email))
    return render_template('register.html', categories=CATEGORIES, priorities=PRIORITIES)

@app.route('/track-complaint', methods=['GET','POST'])
def track_complaint():
    complaint = None
    cid = request.values.get('cid','').strip()
    email = request.values.get('email','').strip().lower()
    if cid and email:
        complaint = Complaint.query.filter_by(complaint_id=cid, email=email).first()
        if not complaint:
            flash('No complaint found with that ID and email.', 'danger')
    return render_template('track.html', complaint=complaint, statuses=STATUSES,
                           cid=cid, email=email)

@app.route('/dashboard')
def dashboard():
    email = request.args.get('email','').strip().lower()
    complaints = []
    if email:
        complaints = Complaint.query.filter_by(email=email).order_by(Complaint.created_at.desc()).all()
    return render_template('dashboard.html', complaints=complaints, email=email)

@app.route('/dashboard/export')
def dashboard_export():
    email = request.args.get('email','').strip().lower()
    if not email: abort(400)
    rows = [c.to_dict() for c in Complaint.query.filter_by(email=email).all()]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False, sheet_name='Complaints')
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'complaints_{email}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/receipt/<cid>')
def receipt(cid):
    c = Complaint.query.filter_by(complaint_id=cid).first_or_404()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle('t', parent=styles['Title'], textColor=colors.HexColor('#0A58CA'))
    story = [Paragraph('Digital Complaint Management System', title),
             Paragraph('Official Complaint Receipt', styles['Heading3']),
             Spacer(1, 8)]
    data = [['Complaint ID', c.complaint_id],
            ['Name', c.name], ['Email', c.email], ['Phone', c.phone or '-'],
            ['Title', c.title], ['Category', c.category],
            ['Priority', c.priority], ['Status', c.status],
            ['Location', c.location or '-'],
            ['Submitted', c.created_at.strftime('%Y-%m-%d %H:%M UTC')]]
    t = Table(data, colWidths=[45*mm, 110*mm])
    t.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#DEE2E6')),
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#F8F9FA')),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('TEXTCOLOR',(0,0),(-1,-1),colors.HexColor('#21252B')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('PADDING',(0,0),(-1,-1),6),
    ]))
    story.append(t); story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Description</b>', styles['Heading4']))
    story.append(Paragraph(c.description.replace('\n','<br/>'), styles['Normal']))
    story.append(Spacer(1, 12))
    qr_url = url_for('track_complaint', cid=c.complaint_id, email=c.email, _external=True)
    img = qrcode.make(qr_url)
    qbuf = io.BytesIO(); img.save(qbuf, format='PNG'); qbuf.seek(0)
    story.append(Paragraph('<b>Track this complaint:</b>', styles['Normal']))
    story.append(RLImage(qbuf, width=35*mm, height=35*mm))
    story.append(Paragraph(qr_url, styles['Italic']))
    doc.build(story)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'{c.complaint_id}.pdf',
                     mimetype='application/pdf')

# ---------- Auth ----------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
        if u and u.check_password(request.form.get('password','')):
            login_user(u)
            return redirect(url_for('admin'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ---------- Admin ----------
@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin: abort(403)
    q = Complaint.query
    fcat = request.args.get('category','')
    fstatus = request.args.get('status','')
    fprio = request.args.get('priority','')
    fsearch = request.args.get('q','').strip()
    if fcat: q = q.filter_by(category=fcat)
    if fstatus: q = q.filter_by(status=fstatus)
    if fprio: q = q.filter_by(priority=fprio)
    if fsearch:
        like = f'%{fsearch}%'
        q = q.filter(db.or_(Complaint.complaint_id.ilike(like),
                            Complaint.title.ilike(like),
                            Complaint.email.ilike(like)))
    complaints = q.order_by(Complaint.created_at.desc()).all()

    total = Complaint.query.count()
    by_status = {s: Complaint.query.filter_by(status=s).count() for s in STATUSES}
    by_category = {c: Complaint.query.filter_by(category=c).count() for c in CATEGORIES}
    # last 7 days
    today = datetime.utcnow().date()
    daily_labels, daily_counts = [], []
    for i in range(6,-1,-1):
        d = today - timedelta(days=i)
        nxt = d + timedelta(days=1)
        n = Complaint.query.filter(Complaint.created_at>=d, Complaint.created_at<nxt).count()
        daily_labels.append(d.strftime('%b %d')); daily_counts.append(n)

    return render_template('admin.html', complaints=complaints, total=total,
                           by_status=by_status, by_category=by_category,
                           daily_labels=daily_labels, daily_counts=daily_counts,
                           categories=CATEGORIES, statuses=STATUSES,
                           priorities=PRIORITIES, departments=DEPARTMENTS,
                           filters={'category':fcat,'status':fstatus,
                                    'priority':fprio,'q':fsearch})

@app.route('/admin/update/<int:cid>', methods=['POST'])
@login_required
def admin_update(cid):
    if not current_user.is_admin: abort(403)
    c = Complaint.query.get_or_404(cid)
    f = request.form
    c.status = f.get('status', c.status)
    c.priority = f.get('priority', c.priority)
    c.assigned_department = f.get('assigned_department', c.assigned_department)
    c.resolution_notes = f.get('resolution_notes', c.resolution_notes)
    note = f.get('note','').strip()
    if note:
        db.session.add(AdminNote(complaint_id=c.id, note=note))
    db.session.commit()
    flash('Complaint updated', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/export')
@login_required
def admin_export():
    if not current_user.is_admin: abort(403)
    rows = [c.to_dict() for c in Complaint.query.all()]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False, sheet_name='Complaints')
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='all_complaints.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/api/complaints')
def api_complaints():
    return jsonify([c.to_dict() for c in Complaint.query.order_by(Complaint.created_at.desc()).limit(200).all()])

@app.route('/features')
def features(): return render_template('features.html')
@app.route('/about')
def about(): return render_template('about.html')
@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you! Your message has been received.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

# ---------- Bootstrap ----------
def seed():
    if not User.query.filter_by(email='admin@dcms.gov').first():
        u = User(name='System Admin', email='admin@dcms.gov', is_admin=True)
        u.set_password('admin123')
        db.session.add(u); db.session.commit()
    if Complaint.query.count() == 0:
        samples = [
            ('Ravi Kumar','ravi@example.com','9876543210','Streetlight not working','Infrastructure',
             'Streetlight on 3rd Cross Road has been off for 2 weeks.','Sector 12','High','In Progress','Public Works'),
            ('Priya Sharma','priya@example.com','9876500001','Water supply disrupted','Water',
             'No water supply for the last 3 days in our apartment.','Green Park','Critical','Assigned','Water Board'),
            ('Amit Verma','amit@example.com','9876500002','Frequent power cuts','Electricity',
             'Power cuts every evening for 2 hours.','Block B','Medium','Under Review','Electricity Board'),
            ('Sneha R','sneha@example.com','9876500003','Slow internet','Internet',
             'Broadband speed dropped to <1 Mbps.','HSR Layout','Low','Resolved','IT Cell'),
            ('Karthik N','karthik@example.com','9876500004','Pothole on main road','Infrastructure',
             'Large pothole causing accidents.','MG Road','High','Submitted','Public Works'),
            ('Meena P','meena@example.com','9876500005','Hospital cleanliness','Healthcare',
             'Government hospital not maintaining hygiene.','Civil Lines','Medium','In Progress','Health Dept'),
            ('Arjun S','arjun@example.com','9876500006','Bus delay','Transport',
             'Bus route 45 is consistently late.','Central Station','Low','Closed','Transport Dept'),
            ('Divya M','divya@example.com','9876500007','School fee dispute','Education',
             'Unfair fee hike notice received.','School Lane','Medium','Under Review','Education Dept'),
        ]
        now = datetime.utcnow()
        for i,(n,e,p,t,cat,d,loc,pr,st,dep) in enumerate(samples):
            c = Complaint(complaint_id=gen_complaint_id(), name=n, email=e, phone=p,
                          title=t, category=cat, description=d, location=loc,
                          priority=pr, status=st, assigned_department=dep,
                          created_at=now - timedelta(days=i, hours=i*2),
                          updated_at=now - timedelta(days=max(i-1,0)))
            db.session.add(c)
        db.session.commit()

with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
