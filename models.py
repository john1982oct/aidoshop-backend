from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Member(db.Model):
    __tablename__ = "members"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    gender = db.Column(db.String(20))
    consent_to_emails = db.Column(db.Boolean, default=True)
    focus_areas = db.Column(db.Text, nullable=True)  # NEW: e.g. "Career,Wealth"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    birth_data = db.relationship("MemberBirthData", backref="member", uselist=False)
    energy_map = db.relationship("EnergyMap", backref="member", uselist=False)


class MemberBirthData(db.Model):
    __tablename__ = "member_birth_data"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    time_of_birth = db.Column(db.Time)
    birth_city = db.Column(db.String(255))
    time_zone = db.Column(db.String(64))


class EnergyMap(db.Model):
    __tablename__ = "energy_map"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)
    energy_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
