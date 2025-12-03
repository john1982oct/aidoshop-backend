from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Member(db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)

    gender = db.Column(db.String(50), nullable=True)
    consent_to_emails = db.Column(db.Boolean, default=True)

    # What the member cares about (Career/Wealth/Relationship/Health/Others)
    focus_areas = db.Column(db.Text, nullable=True)

    # NEW: tracking fields
    source_page = db.Column(db.String(255), nullable=True)   # e.g. which page/form
    ip_address  = db.Column(db.String(45), nullable=True)    # IPv4/IPv6
    country_code = db.Column(db.String(2), nullable=True)    # e.g. 'SG', 'US'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One-to-one helper relationships (keep as before)
    birth_data = db.relationship("MemberBirthData", backref="member", uselist=False)
    energy_map = db.relationship("EnergyMap", backref="member", uselist=False)


class MemberBirthData(db.Model):
    __tablename__ = "member_birth_data"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)

    date_of_birth = db.Column(db.Date, nullable=False)
    time_of_birth = db.Column(db.Time, nullable=True)
    birth_city = db.Column(db.String(255), nullable=True)
    time_zone = db.Column(db.String(64), nullable=True)


class EnergyMap(db.Model):
    __tablename__ = "energy_map"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)

    energy_type = db.Column(db.String(64), nullable=False)
    notes = db.Column(db.Text, nullable=True)
