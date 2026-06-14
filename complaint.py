from datetime import datetime
from . import db

class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(40))
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200))
    document = db.Column(db.String(255))
    priority = db.Column(db.String(20), default='Medium')
    status = db.Column(db.String(40), default='Submitted')
    assigned_department = db.Column(db.String(120))
    resolution_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.relationship('AdminNote', backref='complaint', cascade='all,delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'complaint_id': self.complaint_id,
            'name': self.name, 'email': self.email, 'phone': self.phone,
            'title': self.title, 'category': self.category,
            'description': self.description, 'location': self.location,
            'priority': self.priority, 'status': self.status,
            'assigned_department': self.assigned_department,
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M'),
        }

class AdminNote(db.Model):
    __tablename__ = 'admin_notes'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
